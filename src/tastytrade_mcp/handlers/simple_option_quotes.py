"""Simple option quotes handler that uses exact symbols."""

import os
import asyncio
from typing import Any, Dict, List
import mcp.types as types
import httpx
from tastytrade_mcp.services.websocket_quotes import WebSocketQuoteService, DXFeedSymbolConverter
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


async def handle_get_option_quotes(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get real-time quotes for option symbols directly.

    Args:
        arguments: Dictionary containing:
            - symbols: Comma-separated list of exact option symbols (e.g., "AMD  251121P00165000")
            - duration: How long to stream quotes in seconds (default: 5)

    Returns:
        List containing TextContent with quote data
    """
    symbols_str = arguments.get("symbols", "")
    duration = arguments.get("duration", 5)

    if not symbols_str:
        return [types.TextContent(
            type="text",
            text="Error: At least one symbol is required. Use exact option symbols like 'AMD  251121P00165000'"
        )]

    symbols = [s.strip() for s in symbols_str.split(",")]

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

        # Use simple direct approach like working test
        base_url = "https://api.tastyworks.com" if use_production else "https://api.cert.tastyworks.com"

        # Refresh token to get access token
        response = httpx.post(
            f"{base_url}/oauth/token",
            data={
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': client_id,
                'client_secret': client_secret
            }
        )

        if response.status_code != 200:
            return [types.TextContent(
                type="text",
                text=f"Error: OAuth token refresh failed: {response.text}"
            )]

        token_data = response.json()
        access_token = token_data['access_token']

        # Get WebSocket token using access token
        ws_response = httpx.get(
            f"{base_url}/api-quote-tokens",
            headers={'Authorization': f'Bearer {access_token}'}
        )

        if ws_response.status_code != 200:
            return [types.TextContent(
                type="text",
                text=f"Error: Failed to get quote token: {ws_response.text}"
            )]

        ws_data = ws_response.json()['data']
        ws_token = ws_data['token']
        ws_url = ws_data.get('dxlink-url', 'wss://tasty-openapi-ws.dxfeed.com/realtime')

        # Convert symbols to DXFeed format
        dxfeed_symbols = []
        symbol_map = {}  # Map DXFeed back to original

        for symbol in symbols:
            if '  ' in symbol:  # Option symbol with double space
                dxfeed_symbol = DXFeedSymbolConverter.option_to_dxfeed(symbol)
            else:  # Equity or already converted
                dxfeed_symbol = DXFeedSymbolConverter.equity_to_dxfeed(symbol)

            dxfeed_symbols.append(dxfeed_symbol)
            symbol_map[dxfeed_symbol] = symbol

        # Create WebSocket service
        ws_service = WebSocketQuoteService(ws_token, ws_url)

        # Connect and get quotes
        if not await ws_service.connect():
            return [types.TextContent(
                type="text",
                text="Error: Failed to connect to quote stream"
            )]

        try:
            # Subscribe to quotes
            if not await ws_service.subscribe_quotes(dxfeed_symbols):
                return [types.TextContent(
                    type="text",
                    text="Error: Failed to subscribe to symbols"
                )]

            # Wait for quotes
            await asyncio.sleep(duration)

            # Get collected quotes
            quotes_data = []
            for dxfeed_symbol in dxfeed_symbols:
                quote = await ws_service.get_quote(dxfeed_symbol)
                if quote:
                    # Map back to original symbol
                    original_symbol = symbol_map.get(dxfeed_symbol, dxfeed_symbol)
                    quote['symbol'] = original_symbol
                    quotes_data.append(quote)

            # Format output
            result = "Real-Time Option Quotes\n"
            result += "="*60 + "\n\n"

            if not quotes_data:
                result += "⚠️ No quotes received. This could mean:\n"
                result += "  - Markets are closed\n"
                result += "  - Invalid symbols\n"
                result += "  - Connection issues\n\n"
                result += f"Attempted symbols: {', '.join(symbols)}\n"
                result += f"DXFeed format: {', '.join(dxfeed_symbols)}\n\n"
                result += "💡 Tip: Get exact symbols from your positions using get_positions tool"
            else:
                result += f"✅ Received {len(quotes_data)} quotes:\n\n"

                for quote in quotes_data:
                    symbol = quote['symbol']
                    bid = quote.get('bid', 0)
                    ask = quote.get('ask', 0)
                    bid_size = quote.get('bidSize', 0)
                    ask_size = quote.get('askSize', 0)

                    result += f"📊 {symbol}\n"
                    result += f"  Bid: ${bid:.2f} (Size: {bid_size})\n"
                    result += f"  Ask: ${ask:.2f} (Size: {ask_size})\n"

                    if bid > 0 and ask > 0:
                        mid = (bid + ask) / 2
                        spread = ask - bid
                        result += f"  Mid: ${mid:.2f}\n"
                        result += f"  Spread: ${spread:.2f}\n"

                    # Show contract value for options
                    if '  ' in symbol:
                        contract_bid = bid * 100
                        contract_ask = ask * 100
                        result += f"  Contract Bid: ${contract_bid:.0f}\n"
                        result += f"  Contract Ask: ${contract_ask:.0f}\n"

                    result += "\n"

                result += f"📡 Streamed for {duration} seconds"

            return [types.TextContent(type="text", text=result)]

        finally:
            await ws_service.disconnect()

    except Exception as e:
        logger.error(f"Error getting option quotes: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error getting option quotes: {str(e)}"
        )]