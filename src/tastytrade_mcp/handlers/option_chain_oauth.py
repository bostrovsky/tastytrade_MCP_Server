"""Option chain handler with proper implementation."""
import os
from typing import Any, Dict, List
from datetime import datetime, timedelta
import mcp.types as types
from tastytrade_mcp.services.oauth_client import OAuthHTTPClient
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


def construct_option_symbol(underlying: str, expiration: str, option_type: str, strike: float) -> str:
    """Construct TastyTrade option symbol format.

    Format: SYMBOL  YYMMDDCP00000000
    Example: AAPL  251017P00210000

    Args:
        underlying: Stock symbol (e.g., 'AAPL')
        expiration: Expiration date YYYY-MM-DD (e.g., '2025-10-17')
        option_type: 'call' or 'put'
        strike: Strike price (e.g., 210.0)

    Returns:
        Formatted option symbol
    """
    # Parse date
    exp_date = datetime.strptime(expiration, '%Y-%m-%d')

    # Format: YYMMDD
    date_str = exp_date.strftime('%y%m%d')

    # C for call, P for put
    cp = 'C' if option_type.lower() == 'call' else 'P'

    # Strike with 3 decimals, 8 digits total: 00210000 for $210.00
    strike_int = int(strike * 1000)
    strike_str = f'{strike_int:08d}'

    # TastyTrade format has 2 spaces between ticker and option code
    return f"{underlying}  {date_str}{cp}{strike_str}"


async def handle_get_option_chain(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get option chain for a symbol with specific expiration and strike filters.

    Args:
        arguments: Dictionary containing:
            - symbol: The underlying symbol (required)
            - expiration: Specific expiration date (YYYY-MM-DD) or DTE range
            - min_strike: Minimum strike price
            - max_strike: Maximum strike price
            - option_type: 'call', 'put', or 'both' (default: 'both')
            - format: 'text' or 'json' (default: 'text')

    Returns:
        List containing TextContent with option chain data
    """
    # DEBUG: Confirm this version is running
    logger.warning(f"🔥 NEW VERSION LOADED AT {datetime.now().isoformat()} 🔥")

    symbol = arguments.get("symbol", "").upper()
    expiration = arguments.get("expiration")
    min_strike = arguments.get("min_strike")
    max_strike = arguments.get("max_strike")
    option_type = arguments.get("option_type", "both").lower()
    format_type = arguments.get("format", "text")

    logger.warning(f"🔥 PARAMS: symbol={symbol}, exp={expiration}, min={min_strike}, max={max_strike}, type={option_type}")

    if not symbol:
        return [types.TextContent(
            type="text",
            text="Error: Symbol is required"
        )]

    try:
        # Get OAuth credentials
        client_id = os.environ.get('TASTYTRADE_CLIENT_ID')
        client_secret = os.environ.get('TASTYTRADE_CLIENT_SECRET')
        refresh_token = os.environ.get('TASTYTRADE_REFRESH_TOKEN')
        use_production = os.environ.get('TASTYTRADE_USE_PRODUCTION', 'false').lower() == 'true'

        if not all([client_id, client_secret, refresh_token]):
            return [types.TextContent(
                type="text",
                text="Error: OAuth credentials not configured"
            )]

        async with OAuthHTTPClient(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            sandbox=not use_production
        ) as client:
            filtered_options = []

            # WORKAROUND: If user specified exact expiration + strikes, skip the broken API
            # and construct symbols directly (TastyTrade API has incomplete options chain data)
            if expiration and '-' in expiration and len(expiration) == 10 and (min_strike or max_strike):
                logger.info(f"User specified exact expiration {expiration} + strikes - bypassing API and constructing symbols directly")

                # Generate strikes in $5 increments
                strikes_to_try = []
                if min_strike and max_strike:
                    start = float(min_strike)
                    end = float(max_strike)
                    current = start
                    while current <= end:
                        strikes_to_try.append(current)
                        current += 5.0
                elif min_strike:
                    strikes_to_try = [float(min_strike)]
                elif max_strike:
                    strikes_to_try = [float(max_strike)]

                logger.info(f"Constructing symbols for strikes: {strikes_to_try}")

                for strike in strikes_to_try:
                    types_to_try = []
                    if option_type == 'call':
                        types_to_try = ['call']
                    elif option_type == 'put':
                        types_to_try = ['put']
                    else:
                        types_to_try = ['call', 'put']

                    for opt_type in types_to_try:
                        manual_symbol = construct_option_symbol(symbol, expiration, opt_type, strike)
                        filtered_options.append({
                            'symbol': manual_symbol,
                            'type': opt_type.capitalize(),
                            'strike': strike,
                            'expiration': expiration,
                            'dte': (datetime.strptime(expiration, '%Y-%m-%d') - datetime.now()).days,
                            'manual': True
                        })

                logger.info(f"Constructed {len(filtered_options)} manual option symbols")

            else:
                # Use API for general browsing (no specific expiration/strikes)
                logger.info(f"Using API option chain endpoint for general browsing")
                chain_response = await client.get(f'/option-chains/{symbol}/nested')
                data = chain_response.get('data', {})
                expirations_data = data.get('expirations', [])

                logger.info(f"Retrieved {len(expirations_data)} expirations from API for {symbol}")
                if expirations_data:
                    exp_dates = [exp.get('expiration-date') for exp in expirations_data[:5]]
                    logger.info(f"First 5 expirations: {exp_dates}")

                if not expirations_data:
                    logger.warning(f"No expirations found in API response for {symbol}")
                    return [types.TextContent(
                        type="text",
                        text=f"No options found for {symbol}"
                    )]

                # Filter options from nested structure
                for exp_data in expirations_data:
                    exp_date = exp_data.get('expiration-date')

                    # Filter by expiration if specified
                    if expiration:
                        if '-' in expiration and len(expiration) == 10:  # Specific date YYYY-MM-DD
                            if exp_date != expiration:
                                continue
                        else:  # DTE range like "30-35"
                            try:
                                if '-' in str(expiration):
                                    min_dte, max_dte = map(int, str(expiration).split('-'))
                                else:
                                    min_dte = max_dte = int(expiration)

                                exp_dt = datetime.strptime(exp_date, '%Y-%m-%d')
                                dte = (exp_dt - datetime.now()).days
                                if not (min_dte <= dte <= max_dte):
                                    continue
                            except:
                                pass

                    # Process strikes for this expiration
                    strikes_data = exp_data.get('strikes', [])
                    for strike_data in strikes_data:
                        strike = float(strike_data.get('strike-price', 0))

                        # Filter by strike price
                        if min_strike and strike < float(min_strike):
                            continue
                        if max_strike and strike > float(max_strike):
                            continue

                        # Add call option if requested
                        if option_type in ['call', 'both']:
                            call_symbol = strike_data.get('call')
                            if call_symbol:
                                filtered_options.append({
                                    'symbol': call_symbol,
                                    'type': 'Call',
                                    'strike': strike,
                                    'expiration': exp_date,
                                    'dte': (datetime.strptime(exp_date, '%Y-%m-%d') - datetime.now()).days if exp_date else 0
                                })

                        # Add put option if requested
                        if option_type in ['put', 'both']:
                            put_symbol = strike_data.get('put')
                            if put_symbol:
                                filtered_options.append({
                                    'symbol': put_symbol,
                                    'type': 'Put',
                                    'strike': strike,
                                    'expiration': exp_date,
                                    'dte': (datetime.strptime(exp_date, '%Y-%m-%d') - datetime.now()).days if exp_date else 0
                                })

            # WORKAROUND: If no options found but user specified exact expiration+strike,
            # construct the symbol manually (TastyTrade API bug with weekly options)
            logger.info(f"Filtered options count: {len(filtered_options)}, expiration={expiration}, min_strike={min_strike}, max_strike={max_strike}")

            # Check if user requested a future date that's not in the filtered results
            should_fallback = False
            if expiration and '-' in expiration and len(expiration) == 10:
                requested_date = datetime.strptime(expiration, '%Y-%m-%d')
                # If no options found OR requested date is in the future and not in results
                if not filtered_options:
                    should_fallback = True
                    logger.warning(f"No filtered options - will attempt manual construction")
                elif requested_date > datetime.now():
                    # Check if any filtered option matches the requested expiration
                    has_requested_exp = any(opt['expiration'] == expiration for opt in filtered_options)
                    if not has_requested_exp:
                        should_fallback = True
                        logger.warning(f"Requested future expiration {expiration} not in results - will attempt manual construction")

            if should_fallback and expiration and (min_strike or max_strike):
                logger.warning(f"No options found in chain for {symbol}, attempting manual symbol construction for {expiration}")

                # Check if expiration is a specific date
                if '-' in expiration and len(expiration) == 10:
                    # User wants specific strike(s) - generate range
                    strikes_to_try = []
                    if min_strike and max_strike:
                        # Generate strikes in $5 increments between min and max
                        start = float(min_strike)
                        end = float(max_strike)
                        current = start
                        while current <= end:
                            strikes_to_try.append(current)
                            current += 5.0  # Standard $5 strike increments
                    elif min_strike:
                        strikes_to_try = [float(min_strike)]
                    elif max_strike:
                        strikes_to_try = [float(max_strike)]

                    logger.info(f"Generating manual symbols for strikes: {strikes_to_try}")

                    for strike in strikes_to_try:
                        types_to_try = []
                        if option_type == 'call':
                            types_to_try = ['call']
                        elif option_type == 'put':
                            types_to_try = ['put']
                        else:
                            types_to_try = ['call', 'put']

                        for opt_type in types_to_try:
                            manual_symbol = construct_option_symbol(symbol, expiration, opt_type, strike)
                            filtered_options.append({
                                'symbol': manual_symbol,
                                'type': opt_type.capitalize(),
                                'strike': strike,
                                'expiration': expiration,
                                'dte': (datetime.strptime(expiration, '%Y-%m-%d') - datetime.now()).days,
                                'manual': True  # Flag that this was manually constructed
                            })

                    if filtered_options:
                        logger.info(f"Manually constructed {len(filtered_options)} option symbols")

            # Sort by expiration then strike
            filtered_options.sort(key=lambda x: (x['expiration'], x['strike']))

            # Fetch pricing for filtered options using /market-data/by-type
            if filtered_options:
                # Get symbols for pricing (limit to avoid URL length issues)
                symbols_to_quote = [opt['symbol'] for opt in filtered_options[:100]]
                symbols_param = ','.join(symbols_to_quote)

                try:
                    quote_response = await client.get(
                        '/market-data/by-type',
                        params={'equity-option': symbols_param}
                    )

                    # Build a lookup map of symbol -> quote
                    quotes_by_symbol = {}
                    for quote_item in quote_response.get('data', {}).get('items', []):
                        sym = quote_item.get('symbol')
                        if sym:
                            quotes_by_symbol[sym] = {
                                'bid': quote_item.get('bid'),
                                'ask': quote_item.get('ask'),
                                'mark': quote_item.get('mark'),
                                'last': quote_item.get('last'),
                                'bid-size': quote_item.get('bid-size'),
                                'ask-size': quote_item.get('ask-size')
                            }

                    # Merge pricing into filtered options
                    for opt in filtered_options:
                        quote = quotes_by_symbol.get(opt['symbol'], {})
                        opt['bid'] = quote.get('bid')
                        opt['ask'] = quote.get('ask')
                        opt['mark'] = quote.get('mark')
                        opt['last'] = quote.get('last')
                        opt['bid_size'] = quote.get('bid-size')
                        opt['ask_size'] = quote.get('ask-size')

                except Exception as e:
                    logger.warning(f"Could not fetch pricing for options: {e}")
                    # Continue without pricing - don't fail the whole request

            if format_type == "json":
                import json
                result = json.dumps(filtered_options, indent=2)
            else:
                result = f"Option Chain for {symbol}\n"
                result += "="*60 + "\n"

                if not filtered_options:
                    result += "No options match the specified criteria.\n"
                else:
                    result += f"Found {len(filtered_options)} options\n\n"

                    # Group by expiration
                    current_exp = None
                    for opt in filtered_options[:50]:  # Limit display
                        if opt['expiration'] != current_exp:
                            current_exp = opt['expiration']
                            result += f"\n📅 Expiration: {current_exp} ({opt['dte']} days)\n"
                            result += "-"*60 + "\n"

                        # Show pricing if available
                        bid = opt.get('bid')
                        ask = opt.get('ask')
                        mark = opt.get('mark')
                        manual_flag = " *" if opt.get('manual') else ""

                        if bid and ask:
                            mid = (float(bid) + float(ask)) / 2
                            result += f"  {opt['type']:4} ${opt['strike']:>6.2f} - Bid: ${float(bid):>5.2f} Ask: ${float(ask):>5.2f} Mid: ${mid:>5.2f}{manual_flag}\n"
                        elif mark:
                            result += f"  {opt['type']:4} ${opt['strike']:>6.2f} - Mark: ${float(mark):>5.2f}{manual_flag}\n"
                        else:
                            result += f"  {opt['type']:4} ${opt['strike']:>6.2f} - {opt['symbol']} (no quote){manual_flag}\n"

                    if len(filtered_options) > 50:
                        result += f"\n... and {len(filtered_options) - 50} more options"

                    # Add note about manually constructed symbols
                    if any(opt.get('manual') for opt in filtered_options):
                        result += "\n\n* Symbol manually constructed (not in API chain - known TastyTrade weekly options bug)"

            return [types.TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Error getting option chain: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error getting option chain: {str(e)}"
        )]


async def handle_find_options_by_delta(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Find options by target delta (estimated by % OTM).

    Since we can't get Greeks from the API directly, we estimate:
    - 10 delta put ≈ 12% OTM
    - 16 delta put ≈ 8% OTM
    - 25 delta put ≈ 5% OTM
    - 30 delta put ≈ 4% OTM

    Args:
        arguments: Dictionary containing:
            - symbol: The underlying symbol (required)
            - target_delta: Target delta value (e.g., 10, 16, 25, 30, or -0.30 for -30 delta)
            - option_type: 'call' or 'put' (required)
            - dte_range: Days to expiration range (e.g., "30-35") OR
            - max_dte: Maximum days to expiration (e.g., 45)
            - min_dte: Minimum days to expiration (default: 0)
            - current_price: Current stock price (will fetch if not provided)

    Returns:
        List containing TextContent with matching options
    """
    symbol = arguments.get("symbol", "").upper()
    target_delta_raw = arguments.get("target_delta", 10)
    option_type = arguments.get("option_type", "put").lower()
    dte_range = arguments.get("dte_range")
    max_dte_arg = arguments.get("max_dte")
    min_dte_arg = arguments.get("min_dte", 0)
    current_price = arguments.get("current_price")

    if not symbol:
        return [types.TextContent(
            type="text",
            text="Error: Symbol is required"
        )]

    # Handle delta format: convert -0.30 to 30, or 0.30 to 30
    if isinstance(target_delta_raw, (float, str)):
        try:
            delta_float = float(target_delta_raw)
            # If it's a decimal (like -0.30 or 0.30), convert to percentage
            if abs(delta_float) < 1:
                target_delta = int(abs(delta_float) * 100)
            else:
                target_delta = int(abs(delta_float))
        except ValueError:
            target_delta = 10  # Default
    else:
        target_delta = abs(int(target_delta_raw))

    # Delta to OTM% approximation for puts
    delta_otm_map = {
        5: 18, 8: 13, 10: 12, 12: 10, 16: 8, 20: 6, 25: 5, 30: 4, 35: 3, 40: 2
    }

    # Find closest delta mapping
    closest_delta = min(delta_otm_map.keys(), key=lambda x: abs(x - target_delta))
    target_otm = delta_otm_map[closest_delta]

    try:
        # Parse DTE range
        if dte_range:
            if '-' in str(dte_range):
                min_dte, max_dte = map(int, str(dte_range).split('-'))
            else:
                min_dte = 0
                max_dte = int(dte_range)
        elif max_dte_arg:
            min_dte = int(min_dte_arg)
            max_dte = int(max_dte_arg)
        else:
            # Default range
            min_dte = 0
            max_dte = 45

        # Get OAuth client
        client_id = os.environ.get('TASTYTRADE_CLIENT_ID')
        client_secret = os.environ.get('TASTYTRADE_CLIENT_SECRET')
        refresh_token = os.environ.get('TASTYTRADE_REFRESH_TOKEN')
        use_production = os.environ.get('TASTYTRADE_USE_PRODUCTION', 'false').lower() == 'true'

        async with OAuthHTTPClient(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            sandbox=not use_production
        ) as client:
            # Get option chain using /nested endpoint
            chain_response = await client.get(f'/option-chains/{symbol}/nested')
            data = chain_response.get('data', {})
            expirations_data = data.get('expirations', [])

            # Use provided price or estimate
            if not current_price:
                # For well-known symbols, use rough estimates
                price_estimates = {
                    'AAPL': 254, 'MSFT': 430, 'GOOGL': 170, 'AMZN': 190,
                    'TSLA': 250, 'META': 560, 'NVDA': 120, 'SPY': 570
                }
                current_price = price_estimates.get(symbol, 100)
            else:
                current_price = float(current_price)

            # Find matching options
            matching_options = []

            for exp_data in expirations_data:
                exp_date = exp_data.get('expiration-date')
                if not exp_date:
                    continue

                exp_dt = datetime.strptime(exp_date, '%Y-%m-%d')
                dte = (exp_dt - datetime.now()).days

                # Check DTE
                if not (min_dte <= dte <= max_dte):
                    continue

                # Process strikes
                strikes_data = exp_data.get('strikes', [])
                for strike_data in strikes_data:
                    strike = float(strike_data.get('strike-price', 0))

                    # Get the appropriate option symbol
                    if option_type == 'put':
                        option_symbol = strike_data.get('put')
                        otm_pct = ((current_price - strike) / current_price) * 100
                    else:  # call
                        option_symbol = strike_data.get('call')
                        otm_pct = ((strike - current_price) / current_price) * 100

                    if not option_symbol:
                        continue

                    # Check if close to target OTM%
                    if abs(otm_pct - target_otm) <= 3:  # Within 3% of target
                        matching_options.append({
                            'symbol': option_symbol,
                            'strike': strike,
                            'expiration': exp_date,
                            'dte': dte,
                            'otm_pct': otm_pct,
                            'est_delta': target_delta,
                            'delta_accuracy': 'estimated'
                        })

            # Sort by closest to target OTM
            matching_options.sort(key=lambda x: abs(x['otm_pct'] - target_otm))

            # Format output
            result = f"Options Near {target_delta} Delta for {symbol}\n"
            result += f"Current Price: ${current_price:.2f} (estimated)\n"
            result += f"DTE Range: {min_dte}-{max_dte} days\n"
            result += "="*60 + "\n\n"

            if not matching_options:
                result += f"No {option_type}s found near {target_delta} delta.\n"
                result += f"Try adjusting DTE range (current: {min_dte}-{max_dte}).\n"
            else:
                result += f"Found {len(matching_options)} potential matches:\n\n"
                result += f"{'Strike':>8} {'DTE':>4} {'OTM%':>6} {'Est.Δ':>6} {'Symbol'}\n"
                result += "-"*60 + "\n"

                for opt in matching_options[:10]:
                    result += f"${opt['strike']:>7.2f} {opt['dte']:>4} {opt['otm_pct']:>5.1f}% "
                    result += f"{opt['est_delta']:>5} {opt['symbol']}\n"

                result += "\n⚠️ Note: Delta values are ESTIMATED based on OTM percentage.\n"
                result += "Actual deltas require Greeks from market data during trading hours.\n"
                result += f"\nEstimation used: {target_delta}Δ ≈ {target_otm}% OTM for {option_type}s"

            return [types.TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Error finding options by delta: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error finding options by delta: {str(e)}"
        )]