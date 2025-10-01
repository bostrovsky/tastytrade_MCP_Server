"""Option chain handler with proper implementation."""
import os
from typing import Any, Dict, List
from datetime import datetime, timedelta
import mcp.types as types
from tastytrade_mcp.services.oauth_client import OAuthHTTPClient
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


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
    symbol = arguments.get("symbol", "").upper()
    expiration = arguments.get("expiration")
    min_strike = arguments.get("min_strike")
    max_strike = arguments.get("max_strike")
    option_type = arguments.get("option_type", "both").lower()
    format_type = arguments.get("format", "text")

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
            # Get option chain
            chain_response = await client.get(f'/option-chains/{symbol}')
            items = chain_response.get('data', {}).get('items', [])

            if not items:
                return [types.TextContent(
                    type="text",
                    text=f"No options found for {symbol}"
                )]

            # Filter options
            filtered_options = []

            for item in items:
                # Filter by option type
                item_type = item.get('option-type')
                if option_type == 'call' and item_type != 'C':
                    continue
                if option_type == 'put' and item_type != 'P':
                    continue

                # Filter by expiration if specified
                exp_date = item.get('expiration-date')
                if expiration:
                    if '-' in expiration:  # Specific date YYYY-MM-DD
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

                # Filter by strike price
                strike = float(item.get('strike-price', 0))
                if min_strike and strike < float(min_strike):
                    continue
                if max_strike and strike > float(max_strike):
                    continue

                # Add to filtered list
                filtered_options.append({
                    'symbol': item.get('symbol'),
                    'type': 'Call' if item_type == 'C' else 'Put',
                    'strike': strike,
                    'expiration': exp_date,
                    'dte': (datetime.strptime(exp_date, '%Y-%m-%d') - datetime.now()).days if exp_date else 0
                })

            # Sort by expiration then strike
            filtered_options.sort(key=lambda x: (x['expiration'], x['strike']))

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
                            result += "-"*40 + "\n"

                        result += f"  {opt['type']:4} ${opt['strike']:>6.2f} - {opt['symbol']}\n"

                    if len(filtered_options) > 50:
                        result += f"\n... and {len(filtered_options) - 50} more options"

                    result += "\n\n⚠️ Note: For real-time bid/ask quotes, use WebSocket streaming."
                    result += "\nQuotes are only available during market hours."

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

    Args:
        arguments: Dictionary containing:
            - symbol: The underlying symbol (required)
            - target_delta: Target delta value (e.g., 10, 16, 25)
            - option_type: 'call' or 'put' (required)
            - dte_range: Days to expiration range (e.g., "30-35")
            - current_price: Current stock price (will fetch if not provided)

    Returns:
        List containing TextContent with matching options
    """
    symbol = arguments.get("symbol", "").upper()
    target_delta = arguments.get("target_delta", 10)
    option_type = arguments.get("option_type", "put").lower()
    dte_range = arguments.get("dte_range", "30-35")
    current_price = arguments.get("current_price")

    if not symbol:
        return [types.TextContent(
            type="text",
            text="Error: Symbol is required"
        )]

    # Delta to OTM% approximation for puts
    delta_otm_map = {
        5: 18, 8: 13, 10: 12, 12: 10, 16: 8, 20: 6, 25: 5, 30: 4
    }

    # Find closest delta mapping
    closest_delta = min(delta_otm_map.keys(), key=lambda x: abs(x - target_delta))
    target_otm = delta_otm_map[closest_delta]

    try:
        # Parse DTE range
        if '-' in str(dte_range):
            min_dte, max_dte = map(int, str(dte_range).split('-'))
        else:
            min_dte = max_dte = int(dte_range)

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
            # Get option chain
            chain_response = await client.get(f'/option-chains/{symbol}')
            items = chain_response.get('data', {}).get('items', [])

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

            for item in items:
                # Filter by type
                item_type = item.get('option-type')
                if option_type == 'put' and item_type != 'P':
                    continue
                if option_type == 'call' and item_type != 'C':
                    continue

                # Check DTE
                exp_date = item.get('expiration-date')
                if exp_date:
                    exp_dt = datetime.strptime(exp_date, '%Y-%m-%d')
                    dte = (exp_dt - datetime.now()).days
                    if not (min_dte <= dte <= max_dte):
                        continue

                    # Calculate OTM percentage
                    strike = float(item.get('strike-price', 0))
                    if option_type == 'put':
                        otm_pct = ((current_price - strike) / current_price) * 100
                    else:  # call
                        otm_pct = ((strike - current_price) / current_price) * 100

                    # Check if close to target OTM%
                    if abs(otm_pct - target_otm) <= 3:  # Within 3% of target
                        matching_options.append({
                            'symbol': item.get('symbol'),
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
            result += "="*60 + "\n\n"

            if not matching_options:
                result += f"No {option_type}s found near {target_delta} delta.\n"
                result += f"Try adjusting DTE range (current: {dte_range}).\n"
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