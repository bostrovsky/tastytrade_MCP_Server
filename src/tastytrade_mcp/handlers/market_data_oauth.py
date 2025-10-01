"""Market data handlers using OAuth client directly."""
import os
from typing import Any
import mcp.types as types
from tastytrade_mcp.services.oauth_client import OAuthHTTPClient
from tastytrade_mcp.services.response_parser import ResponseParser
from tastytrade_mcp.utils.logging import get_logger
from tastytrade_mcp.handlers.utils_oauth import ensure_account_number, get_oauth_credentials

logger = get_logger(__name__)


async def handle_search_symbols(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Search for tradable symbols.

    Args:
        arguments: Dictionary containing:
            - query: Search query string
            - limit: Maximum number of results (default 10)
            - format: Optional response format ('text' or 'json')

    Returns:
        List containing TextContent with search results
    """
    query = arguments.get("query", "")
    limit = arguments.get("limit", 10)
    format_type = arguments.get("format", "text")

    if not query:
        return [types.TextContent(
            type="text",
            text="Error: Search query is required"
        )]

    try:
        # Get OAuth credentials from environment
        client_id = os.environ.get('TASTYTRADE_CLIENT_ID')
        client_secret = os.environ.get('TASTYTRADE_CLIENT_SECRET')
        refresh_token = os.environ.get('TASTYTRADE_REFRESH_TOKEN')
        use_production = os.environ.get('TASTYTRADE_USE_PRODUCTION', 'false').lower() == 'true'

        if not all([client_id, client_secret, refresh_token]):
            return [types.TextContent(
                type="text",
                text="Error: OAuth credentials not configured. Please set TASTYTRADE_CLIENT_ID, TASTYTRADE_CLIENT_SECRET, and TASTYTRADE_REFRESH_TOKEN in .env"
            )]

        # Create OAuth client
        async with OAuthHTTPClient(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            sandbox=not use_production
        ) as client:
            # Search for symbols - use path parameter not query param
            search_response = await client.get(f'/symbols/search/{query.upper()}')

            # Parse the response
            items = search_response.get('data', {}).get('items', [])[:limit]

            if format_type == "json":
                import json
                formatted = json.dumps(items, indent=2)
            else:
                if not items:
                    formatted = f"No symbols found matching '{query}'"
                else:
                    formatted = f"Symbol search results for '{query}':\n"
                    for item in items:
                        symbol = item.get('symbol', 'N/A')
                        description = item.get('description', '')
                        exchange = item.get('exchange', '')
                        formatted += f"\n  {symbol}"
                        if description:
                            formatted += f" - {description}"
                        if exchange:
                            formatted += f" ({exchange})"
                        formatted += "\n"

            return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error searching symbols: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error searching symbols: {str(e)}"
        )]


async def handle_get_quotes(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get real-time quotes for symbols.

    Args:
        arguments: Dictionary containing:
            - symbols: Comma-separated list of symbols
            - format: Optional response format ('text' or 'json')

    Returns:
        List containing TextContent with quote data
    """
    symbols_str = arguments.get("symbols", "")
    format_type = arguments.get("format", "text")

    if not symbols_str:
        return [types.TextContent(
            type="text",
            text="Error: At least one symbol is required"
        )]

    # Parse symbols
    symbols = [s.strip().upper() for s in symbols_str.split(",")]

    try:
        # Get OAuth credentials from environment
        client_id = os.environ.get('TASTYTRADE_CLIENT_ID')
        client_secret = os.environ.get('TASTYTRADE_CLIENT_SECRET')
        refresh_token = os.environ.get('TASTYTRADE_REFRESH_TOKEN')
        use_production = os.environ.get('TASTYTRADE_USE_PRODUCTION', 'false').lower() == 'true'

        if not all([client_id, client_secret, refresh_token]):
            return [types.TextContent(
                type="text",
                text="Error: OAuth credentials not configured. Please set TASTYTRADE_CLIENT_ID, TASTYTRADE_CLIENT_SECRET, and TASTYTRADE_REFRESH_TOKEN in .env"
            )]

        # Create OAuth client
        async with OAuthHTTPClient(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            sandbox=not use_production
        ) as client:
            # The TastyTrade API doesn't provide REST endpoints for real-time quotes
            # We need to implement WebSocket streaming via DXLink
            # For now, return informative message about the limitation

            result_text = f"Quote Request for: {', '.join(symbols)}\n"
            result_text += "="*50 + "\n\n"
            result_text += "⚠️ Real-time quotes require WebSocket streaming (DXLink)\n\n"
            result_text += "The TastyTrade API uses WebSocket streaming for market data:\n"
            result_text += "1. Get streaming token via /api-quote-tokens\n"
            result_text += "2. Connect to wss://tasty-openapi-ws.dxfeed.com/realtime\n"
            result_text += "3. Subscribe to symbols for real-time updates\n\n"
            result_text += "Note: Quotes are only available during market hours.\n"
            result_text += "For options, use symbols like: AAPL 251031P00225000\n\n"
            result_text += "To implement: Use the streaming_oauth handler for WebSocket quotes."

            return [types.TextContent(
                type="text",
                text=result_text
            )]

            if format_type == "json":
                import json
                quotes_list = [
                    {
                        'symbol': q.symbol,
                        'bid': q.bid_price,
                        'ask': q.ask_price,
                        'last': q.last_price,
                        'bid_size': q.bid_size,
                        'ask_size': q.ask_size,
                        'volume': q.volume,
                        'open': q.open_price,
                        'high': q.high_price,
                        'low': q.low_price,
                        'close': q.close_price,
                        'change': q.change,
                        'change_percent': q.change_percent
                    }
                    for q in quotes
                ]
                formatted = json.dumps(quotes_list, indent=2)
            else:
                if not quotes:
                    formatted = f"No quotes found for symbols: {', '.join(symbols)}"
                else:
                    formatted = "Market Quotes:\n"
                    for q in quotes:
                        formatted += f"\n{q.symbol}:\n"
                        formatted += f"  Last: ${q.last_price:.2f}\n"
                        formatted += f"  Bid: ${q.bid_price:.2f} x {q.bid_size}\n"
                        formatted += f"  Ask: ${q.ask_price:.2f} x {q.ask_size}\n"
                        formatted += f"  Change: ${q.change:+.2f} ({q.change_percent:+.2f}%)\n"
                        formatted += f"  Volume: {q.volume:,}\n"
                        formatted += f"  Range: ${q.low_price:.2f} - ${q.high_price:.2f}\n"

            return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error getting quotes: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error retrieving quotes: {str(e)}"
        )]