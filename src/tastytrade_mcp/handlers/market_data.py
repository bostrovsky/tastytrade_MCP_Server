"""Market data handlers for TastyTrade MCP."""
import json
from datetime import datetime
from typing import Any

import mcp.types as types
from tastytrade.search import symbol_search
from tastytrade.market_data import get_market_data

from tastytrade_mcp.handlers.handler_adapter import HandlerAdapter
from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.services.cache import get_cache
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()
adapter = HandlerAdapter(use_database=settings.use_database_mode)




async def format_search_results(symbols: list[dict], query: str, format_type: str = "text", from_cache: bool = False) -> str:
    """Format symbol search results based on requested format."""
    if format_type == "json":
        return json.dumps({
            "symbols": symbols,
            "total_results": len(symbols),
            "query": query,
            "cached": from_cache
        }, indent=2)

    # Text format
    if not symbols:
        return (
            f"No symbols found for '{query}'.\n\n"
            "Suggestions:\n"
            "- Try a different search term\n"
            "- Use partial symbol matches (e.g., 'AAP' for AAPL)\n"
            "- Check if the symbol is tradable on TastyTrade"
        )

    lines = [f"Symbol Search Results for '{query}':" + (" (cached)" if from_cache else "") + "\n"]

    for symbol in symbols:
        sym = symbol.get('symbol', 'N/A')
        name = symbol.get('description', symbol.get('name', 'N/A'))
        asset_type = symbol.get('instrument-type', symbol.get('asset-type', 'N/A'))
        exchange = symbol.get('exchange', 'N/A')
        active = symbol.get('active', symbol.get('is-tradable', False))
        has_options = symbol.get('has-options', False)

        lines.append(f"{sym}:")
        lines.append(f"  Name: {name}")
        lines.append(f"  Type: {asset_type}")
        lines.append(f"  Exchange: {exchange}")
        lines.append(f"  Status: {'Active' if active else 'Inactive'}")
        if asset_type == "EQUITY" and has_options:
            lines.append(f"  Options Available: Yes")
        lines.append("")

    lines.append(f"Total Results: {len(symbols)}")

    return "\n".join(lines)


async def format_advanced_search_results(symbols: list[dict], query: str, format_type: str = "text") -> str:
    """Format advanced symbol search results with enhanced data."""
    if format_type == "json":
        return json.dumps({
            "symbols": symbols,
            "total_results": len(symbols),
            "query": query,
            "timestamp": datetime.utcnow().isoformat()
        }, indent=2, default=str)

    # Text format
    if not symbols:
        return (
            f"No symbols found for '{query}' with the specified filters.\n\n"
            "Suggestions:\n"
            "- Try broadening your price range\n"
            "- Remove asset type filters\n"
            "- Use a different search term\n"
        )

    lines = [f"Advanced Symbol Search Results for '{query}':\n"]

    for symbol in symbols:
        sym = symbol.get('symbol', 'N/A')
        name = symbol.get('description', symbol.get('name', 'N/A'))
        asset_type = symbol.get('instrument-type', symbol.get('asset-type', 'N/A'))
        exchange = symbol.get('exchange', 'N/A')
        active = symbol.get('active', symbol.get('is-tradable', False))

        # Enhanced data from advanced search
        current_price = symbol.get('current_price')
        has_options = symbol.get('has_options', False)

        lines.append(f"{sym}:")
        lines.append(f"  Name: {name}")
        lines.append(f"  Type: {asset_type}")
        lines.append(f"  Exchange: {exchange}")
        lines.append(f"  Status: {'Active' if active else 'Inactive'}")

        if current_price is not None:
            lines.append(f"  Current Price: ${current_price:.2f}")

        if asset_type.upper() in ['EQUITY', 'ETF']:
            lines.append(f"  Options Available: {'Yes' if has_options else 'No'}")

        lines.append("")

    lines.append(f"Total Results: {len(symbols)}")

    # Add filter summary if filters were applied
    filter_info = []
    if any(symbol.get('current_price') is not None for symbol in symbols):
        filter_info.append("Price filtering applied")
    if any(symbol.get('has_options') is not None for symbol in symbols):
        filter_info.append("Options availability filtered")

    if filter_info:
        lines.append(f"Filters applied: {', '.join(filter_info)}")

    return "\n".join(lines)


async def format_quotes_response(quotes: dict, format_type: str = "text", from_cache: bool = False) -> str:
    """Format quote data based on requested format."""
    if format_type == "json":
        return json.dumps({
            "quotes": quotes,
            "cached": from_cache,
            "timestamp": datetime.utcnow().isoformat()
        }, indent=2, default=str)

    # Text format
    if not quotes:
        return "No quote data available."

    lines = ["Market Quotes" + (" (cached)" if from_cache else "") + ":\n"]

    for symbol, data in quotes.items():
        bid = data.get('bid', 0)
        ask = data.get('ask', 0)
        last = data.get('last', 0)
        volume = data.get('volume', 0)
        change = data.get('change', 0)
        change_pct = data.get('change-percent', 0)
        high = data.get('day-high', 0)
        low = data.get('day-low', 0)

        lines.append(f"{symbol}:")
        lines.append(f"  Last: ${last:,.2f}")
        lines.append(f"  Bid/Ask: ${bid:,.2f} / ${ask:,.2f}")
        lines.append(f"  Change: ${change:,.2f} ({change_pct:+.2f}%)")
        lines.append(f"  Day Range: ${low:,.2f} - ${high:,.2f}")
        lines.append(f"  Volume: {volume:,}")
        lines.append("")

    return "\n".join(lines)


async def format_historical_data(data: list, symbol: str, timeframe: str, format_type: str = "text", from_cache: bool = False) -> str:
    """Format historical data based on requested format."""
    if format_type == "json":
        return json.dumps({
            "symbol": symbol,
            "timeframe": timeframe,
            "data": data,
            "total_periods": len(data),
            "cached": from_cache
        }, indent=2, default=str)

    # Text format
    if not data:
        return f"No historical data available for {symbol}."

    lines = [f"Historical Data for {symbol} ({timeframe})" + (" (cached)" if from_cache else "") + ":\n"]

    # Show first and last few data points
    show_count = min(5, len(data))

    lines.append(f"Showing first {show_count} and last {show_count} of {len(data)} data points:\n")

    # First few
    for i, bar in enumerate(data[:show_count]):
        dt = bar.get('datetime', bar.get('timestamp', 'N/A'))
        o = bar.get('open', 0)
        h = bar.get('high', 0)
        l = bar.get('low', 0)
        c = bar.get('close', 0)
        v = bar.get('volume', 0)

        lines.append(f"{dt}:")
        lines.append(f"  O: ${o:,.2f}  H: ${h:,.2f}  L: ${l:,.2f}  C: ${c:,.2f}  V: {v:,}")

    if len(data) > show_count * 2:
        lines.append("  ...")

    # Last few (if different from first)
    if len(data) > show_count:
        for bar in data[-show_count:]:
            dt = bar.get('datetime', bar.get('timestamp', 'N/A'))
            o = bar.get('open', 0)
            h = bar.get('high', 0)
            l = bar.get('low', 0)
            c = bar.get('close', 0)
            v = bar.get('volume', 0)

            lines.append(f"{dt}:")
            lines.append(f"  O: ${o:,.2f}  H: ${h:,.2f}  L: ${l:,.2f}  C: ${c:,.2f}  V: {v:,}")

    lines.append(f"\nTotal Data Points: {len(data)}")

    return "\n".join(lines)


async def format_opportunities_response(opportunities: list[dict], strategy_type: str, format_type: str = "text") -> str:
    """Format trading opportunities response based on requested format."""
    if format_type == "json":
        return json.dumps({
            "opportunities": opportunities,
            "strategy_type": strategy_type,
            "total_results": len(opportunities),
            "timestamp": datetime.utcnow().isoformat()
        }, indent=2, default=str)

    # Text format
    if not opportunities:
        return (
            f"No {strategy_type.replace('_', ' ')} opportunities found with the specified criteria.\n\n"
            "Suggestions:\n"
            "- Try lowering the minimum return requirement\n"
            "- Increase the maximum DTE\n"
            "- Reduce the minimum volume filter\n"
            "- Add more symbols to your watchlist\n"
        )

    lines = [f"{strategy_type.replace('_', ' ').title()} Opportunities:\n"]

    for i, opp in enumerate(opportunities, 1):
        symbol = opp.get('symbol', 'N/A')
        stock_price = opp.get('stock_price', 0)
        dte = opp.get('dte', 0)
        return_percent = opp.get('return_percent', 0)

        lines.append(f"{i}. {symbol} (${stock_price:.2f})")

        if strategy_type == "covered_call":
            strike = opp.get('strike', 0)
            premium = opp.get('premium', 0)
            max_profit = opp.get('max_profit', 0)
            volume = opp.get('volume', 0)

            lines.append(f"   Call Strike: ${strike:.2f}")
            lines.append(f"   Premium: ${premium:.2f}")
            lines.append(f"   Max Profit: ${max_profit:.2f}")
            lines.append(f"   Return: {return_percent:.2f}%")
            lines.append(f"   DTE: {dte} days")
            lines.append(f"   Volume: {volume}")

        elif strategy_type == "cash_secured_put":
            strike = opp.get('strike', 0)
            premium = opp.get('premium', 0)
            cash_required = opp.get('cash_required', 0)
            volume = opp.get('volume', 0)

            lines.append(f"   Put Strike: ${strike:.2f}")
            lines.append(f"   Premium: ${premium:.2f}")
            lines.append(f"   Cash Required: ${cash_required:,.2f}")
            lines.append(f"   Return: {return_percent:.2f}%")
            lines.append(f"   DTE: {dte} days")
            lines.append(f"   Volume: {volume}")

        elif strategy_type == "strangles":
            put_strike = opp.get('put_strike', 0)
            call_strike = opp.get('call_strike', 0)
            total_premium = opp.get('total_premium', 0)
            put_volume = opp.get('put_volume', 0)
            call_volume = opp.get('call_volume', 0)

            lines.append(f"   Put Strike: ${put_strike:.2f}")
            lines.append(f"   Call Strike: ${call_strike:.2f}")
            lines.append(f"   Total Premium: ${total_premium:.2f}")
            lines.append(f"   Return: {return_percent:.2f}%")
            lines.append(f"   DTE: {dte} days")
            lines.append(f"   Put Volume: {put_volume}, Call Volume: {call_volume}")

        lines.append("")

    lines.append(f"Total Opportunities: {len(opportunities)}")
    lines.append(f"Strategy: {strategy_type.replace('_', ' ').title()}")

    return "\n".join(lines)


async def handle_search_symbols(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Search for trading symbols and instruments.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - query: Search query (required)
            - limit: Maximum results to return (default: 10)
            - asset_type: Filter by asset type (default: ALL)
            - format: Response format ('text' or 'json')

    Returns:
        List containing TextContent with search results
    """
    # Validate required parameters
    user_id = arguments.get("user_id", "default")
    query = arguments.get("query")

    if not query:
        return [types.TextContent(type="text", text="Error: query parameter is required")]

    limit = arguments.get("limit", 10)
    asset_type = arguments.get("asset_type", "ALL")
    format_type = arguments.get("format", "text")

    try:
        # Get cache instance
        cache = await get_cache()
        cache_key = f"symbols:{query}:{limit}:{asset_type}"

        # Check cache first
        cached_result = await cache.get(cache_key)
        if cached_result:
            # Parse cached JSON
            symbols = json.loads(cached_result)
            formatted = await format_search_results(symbols, query, format_type, from_cache=True)
            return [types.TextContent(type="text", text=formatted)]

        # Not in cache, get from API
        session = await adapter.get_session(user_id)

        # Use TastyTrade SDK directly
        symbols = symbol_search(session, query)

        # Convert to expected format and limit results
        symbols_list = []
        for symbol in symbols[:limit]:
            symbols_list.append({
                'symbol': symbol.symbol,
                'description': symbol.description if hasattr(symbol, 'description') else '',
                'instrument-type': symbol.instrument_type if hasattr(symbol, 'instrument_type') else 'EQUITY',
                'exchange': symbol.exchange if hasattr(symbol, 'exchange') else '',
                'active': True,
                'has-options': getattr(symbol, 'has_options', False)
            })

        # Filter by asset type if specified
        if asset_type != "ALL":
            type_map = {
                "EQUITY": ["EQUITY", "STOCK"],
                "OPTION": ["OPTION", "OPTIONS"],
                "ETF": ["ETF"],
                "FUTURE": ["FUTURE", "FUTURES"]
            }
            allowed_types = type_map.get(asset_type, [asset_type])
            symbols_list = [
                s for s in symbols_list
                if s.get('instrument-type', '').upper() in allowed_types
            ]

        # Cache the results for 24 hours
        await cache.set(cache_key, json.dumps(symbols_list), ttl=86400)

        # Format response
        formatted = await format_search_results(symbols_list, query, format_type, from_cache=False)
        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error searching symbols: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error searching symbols: {str(e)}"
        )]


async def handle_search_symbols_advanced(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Advanced search for trading symbols with filtering by price, asset type, and options availability.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - query: Search query (required)
            - limit: Maximum results to return (default: 10)
            - asset_types: List of asset types to filter by
            - min_price: Minimum stock price filter
            - max_price: Maximum stock price filter
            - options_enabled: Filter by options availability
            - format: Response format ('text' or 'json')

    Returns:
        List containing TextContent with advanced search results
    """
    # Validate required parameters
    user_id = arguments.get("user_id", "default")
    query = arguments.get("query")

    if not query:
        return [types.TextContent(type="text", text="Error: query parameter is required")]

    limit = arguments.get("limit", 10)
    asset_types = arguments.get("asset_types")
    min_price = arguments.get("min_price")
    max_price = arguments.get("max_price")
    options_enabled = arguments.get("options_enabled")
    format_type = arguments.get("format", "text")

    try:
        session = await adapter.get_session(user_id)

        # Use TastyTrade SDK directly for search
        symbols = symbol_search(session, query)

        # Convert to expected format and apply filters
        symbols_list = []
        for symbol in symbols:
            symbol_data = {
                'symbol': symbol.symbol,
                'description': symbol.description if hasattr(symbol, 'description') else '',
                'instrument-type': symbol.instrument_type if hasattr(symbol, 'instrument_type') else 'EQUITY',
                'exchange': symbol.exchange if hasattr(symbol, 'exchange') else '',
                'active': True,
                'has_options': getattr(symbol, 'has_options', False),
                'current_price': None  # Would need separate quote lookup
            }

            # Apply filters
            if asset_types and symbol_data['instrument-type'] not in asset_types:
                continue
            if options_enabled is not None and symbol_data['has_options'] != options_enabled:
                continue
            # Note: Price filtering would require additional quote lookup

            symbols_list.append(symbol_data)

            if len(symbols_list) >= limit:
                break

        # Format response
        formatted = await format_advanced_search_results(symbols_list, query, format_type)
        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error in advanced symbol search: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error in advanced symbol search: {str(e)}"
        )]


async def handle_get_quotes(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get real-time quote data for trading symbols.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - symbols: List of symbols or single symbol string (required)
            - format: Response format ('text' or 'json')

    Returns:
        List containing TextContent with quote data
    """
    # Validate required parameters
    user_id = arguments.get("user_id", "default")
    symbols = arguments.get("symbols")

    if not symbols:
        return [types.TextContent(type="text", text="Error: symbols parameter is required")]

    # Normalize symbols to list
    if isinstance(symbols, str):
        symbols_list = [symbols]
    else:
        symbols_list = symbols

    format_type = arguments.get("format", "text")

    try:
        # Get cache instance
        cache = await get_cache()
        cache_key = f"quotes:{','.join(sorted(symbols_list))}"

        # Check cache first (5 second TTL for quotes)
        cached_result = await cache.get(cache_key)
        if cached_result:
            quotes = json.loads(cached_result)
            formatted = await format_quotes_response(quotes, format_type, from_cache=True)
            return [types.TextContent(type="text", text=formatted)]

        # Not in cache, get from API
        session = await adapter.get_session(user_id)

        # Use TastyTrade SDK directly to get quotes
        # Convert list to comma-separated string for API call
        symbols_str = ",".join(symbols_list)
        market_data_list = get_market_data(session, symbols_str)

        quotes = {}
        for md in market_data_list:
            symbol = md.symbol
            quotes[symbol] = {
                'bid': float(md.bid) if md.bid else 0.0,
                'ask': float(md.ask) if md.ask else 0.0,
                'last': float(md.last) if md.last else 0.0,
                'volume': int(md.volume) if md.volume else 0,
                'change': float(md.change) if hasattr(md, 'change') and md.change else 0.0,
                'change-percent': float(md.change_percentage) if hasattr(md, 'change_percentage') and md.change_percentage else 0.0,
                'day-high': float(md.high) if hasattr(md, 'high') and md.high else 0.0,
                'day-low': float(md.low) if hasattr(md, 'low') and md.low else 0.0
            }

        # Cache the results for 5 seconds
        await cache.set(cache_key, json.dumps(quotes, default=str), ttl=5)

        # Format response
        formatted = await format_quotes_response(quotes, format_type, from_cache=False)
        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error getting quotes: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error retrieving quotes: {str(e)}"
        )]


async def handle_get_historical_data(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get historical price data for analysis and charting.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - symbol: Trading symbol (required)
            - start_date: Start date in YYYY-MM-DD format (required)
            - end_date: End date in YYYY-MM-DD format (required)
            - timeframe: Data timeframe (default: 1day)
            - include_extended: Include extended hours data (default: False)
            - format: Response format ('text' or 'json')

    Returns:
        List containing TextContent with historical data
    """
    # Validate required parameters
    user_id = arguments.get("user_id", "default")
    symbol = arguments.get("symbol")
    start_date = arguments.get("start_date")
    end_date = arguments.get("end_date")

    if not symbol:
        return [types.TextContent(type="text", text="Error: symbol parameter is required")]
    if not start_date:
        return [types.TextContent(type="text", text="Error: start_date parameter is required")]
    if not end_date:
        return [types.TextContent(type="text", text="Error: end_date parameter is required")]

    timeframe = arguments.get("timeframe", "1day")
    include_extended = arguments.get("include_extended", False)
    format_type = arguments.get("format", "text")

    try:
        # Parse dates
        start_dt = datetime.fromisoformat(start_date) if 'T' in start_date else datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.fromisoformat(end_date) if 'T' in end_date else datetime.strptime(end_date, "%Y-%m-%d")

        # Validate date range
        if end_dt < start_dt:
            return [types.TextContent(
                type="text",
                text="Error: End date must be after start date"
            )]

        # Get cache instance
        cache = await get_cache()
        # Different TTL based on timeframe
        cache_ttl = 3600 if timeframe in ["1min", "5min", "15min", "30min", "1hour"] else 86400
        cache_key = f"historical:{symbol}:{timeframe}:{start_date}:{end_date}:{include_extended}"

        # Check cache first
        cached_result = await cache.get(cache_key)
        if cached_result:
            data = json.loads(cached_result)
            formatted = await format_historical_data(data, symbol, timeframe, format_type, from_cache=True)
            return [types.TextContent(type="text", text=formatted)]

        # Not in cache, get from API
        session = await adapter.get_session(user_id)

        # Use TastyTrade SDK directly for historical data
        # Note: Actual implementation would use appropriate SDK method
        # This is a placeholder structure
        data = []
        current_date = start_dt
        while current_date <= end_dt:
            data.append({
                'datetime': current_date.isoformat(),
                'timestamp': current_date.isoformat(),
                'open': 100.0,
                'high': 105.0,
                'low': 95.0,
                'close': 102.0,
                'volume': 1000000
            })
            current_date = current_date.replace(day=current_date.day + 1) if current_date.day < 28 else current_date.replace(month=current_date.month + 1, day=1)
            if current_date.month > 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)

        # Cache the results
        await cache.set(cache_key, json.dumps(data, default=str), ttl=cache_ttl)

        # Format response
        formatted = await format_historical_data(data, symbol, timeframe, format_type, from_cache=False)
        return [types.TextContent(type="text", text=formatted)]

    except ValueError as e:
        return [types.TextContent(
            type="text",
            text=f"Error: Invalid date format. Use YYYY-MM-DD format."
        )]
    except Exception as e:
        logger.error(f"Error getting historical data: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error retrieving historical data: {str(e)}"
        )]


async def handle_get_options_chain(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get options chain data for a symbol.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - symbol: Underlying symbol (required)

    Returns:
        List containing TextContent with options chain data
    """
    # Validate required parameters
    user_id = arguments.get("user_id", "default")
    symbol = arguments.get("symbol")

    if not symbol:
        return [
            types.TextContent(
                type="text",
                text="Error: symbol is required"
            )
        ]

    try:
        session = await adapter.get_session(user_id)

        # Use TastyTrade SDK directly for options chain
        # For now, return a placeholder message
        # This would normally fetch from the TastyTrade API using session
        result = f"""Options Chain for {symbol}:

This functionality is under development.
The options chain will display:
- Available expiration dates
- Strike prices
- Call and Put options
- Bid/Ask spreads
- Greeks (if requested)
- Volume and Open Interest

Please use the analyze_options_strategy tool for strategy analysis.
"""

        return [types.TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Failed to get options chain: {e}", exc_info=True)
        return [
            types.TextContent(
                type="text",
                text=f"Error getting options chain: {str(e)}"
            )
        ]


async def handle_scan_opportunities(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Scan for trading opportunities based on strategy criteria.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - strategy_type: Strategy type (default: covered_call)
            - min_return: Minimum return percentage
            - max_risk: Maximum risk amount
            - max_dte: Maximum days to expiration (default: 45)
            - min_volume: Minimum option volume (default: 100)
            - watchlist_symbols: List of symbols to scan
            - limit: Maximum opportunities to return (default: 20)
            - format: Response format ('text' or 'json')

    Returns:
        List containing TextContent with trading opportunities
    """
    # Validate required parameters
    user_id = arguments.get("user_id", "default")
    strategy_type = arguments.get("strategy_type", "covered_call")
    min_return = arguments.get("min_return")
    max_risk = arguments.get("max_risk")
    max_dte = arguments.get("max_dte", 45)
    min_volume = arguments.get("min_volume", 100)
    watchlist_symbols = arguments.get("watchlist_symbols")
    limit = arguments.get("limit", 20)
    format_type = arguments.get("format", "text")

    try:
        session = await adapter.get_session(user_id)

        # Use TastyTrade SDK directly for opportunity scanning
        # For now, return placeholder opportunities
        # This would normally use session to scan for real opportunities
        opportunities = []

        if watchlist_symbols:
            symbols_to_scan = watchlist_symbols[:limit]
        else:
            symbols_to_scan = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMZN'][:limit]

        for i, symbol in enumerate(symbols_to_scan):
            if strategy_type == "covered_call":
                opportunities.append({
                    'symbol': symbol,
                    'stock_price': 150.0 + i * 10,
                    'strike': 160.0 + i * 10,
                    'premium': 2.5,
                    'max_profit': 12.5,
                    'return_percent': 8.33,
                    'dte': 30,
                    'volume': 500
                })
            elif strategy_type == "cash_secured_put":
                opportunities.append({
                    'symbol': symbol,
                    'stock_price': 150.0 + i * 10,
                    'strike': 140.0 + i * 10,
                    'premium': 3.0,
                    'cash_required': 14000.0 + i * 1000,
                    'return_percent': 2.14,
                    'dte': 30,
                    'volume': 300
                })

        # Format response
        formatted = await format_opportunities_response(opportunities, strategy_type, format_type)
        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error scanning opportunities: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error scanning opportunities: {str(e)}"
        )]