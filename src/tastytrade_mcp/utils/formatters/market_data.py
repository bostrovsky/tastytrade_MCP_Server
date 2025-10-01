"""Market data response formatters."""
import json
from datetime import datetime
from typing import Any


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