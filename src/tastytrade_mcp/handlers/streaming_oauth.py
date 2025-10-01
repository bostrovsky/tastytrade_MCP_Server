"""Streaming handlers using OAuth client and WebSocket for DXLink."""
import os
import json
import asyncio
from typing import Any, Optional, Dict
from datetime import datetime
import websockets
import mcp.types as types
from tastytrade_mcp.services.oauth_client import OAuthHTTPClient
from tastytrade_mcp.utils.logging import get_logger
from tastytrade_mcp.handlers.utils_oauth import ensure_account_number, get_oauth_credentials

logger = get_logger(__name__)

# Global streaming state
STREAMING_STATE = {
    "websocket": None,
    "quote_token": None,
    "dxlink_url": None,
    "subscriptions": {},
    "stream_data": {},
    "connected": False,
    "channel": 3,  # Default channel for market data
    "keepalive_task": None,
    "receiver_task": None
}

DXLINK_VERSION = "0.1-DXF-JS/0.3.0"


async def get_quote_token() -> Dict[str, Any]:
    """Get API quote token for streaming."""
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
        # Get quote token - this endpoint DOES work with OAuth!
        response = await client.get('/api-quote-tokens')
        return response.get('data', {})


async def send_keepalive(websocket):
    """Send keepalive messages every 30 seconds."""
    while True:
        try:
            await asyncio.sleep(30)
            if websocket and not websocket.closed:
                await websocket.send(json.dumps({"type": "KEEPALIVE", "channel": 0}))
                logger.debug("Sent keepalive")
        except Exception as e:
            logger.error(f"Keepalive error: {e}")
            break


async def receive_messages(websocket):
    """Receive and store messages from DXLink."""
    while True:
        try:
            message = await websocket.recv()
            data = json.loads(message)

            # Store different message types
            if data.get("type") == "FEED_DATA":
                channel = data.get("channel")
                feed_data = data.get("data", [])

                # Parse the compact format
                if feed_data and len(feed_data) > 1:
                    event_type = feed_data[0]
                    events = feed_data[1]

                    # Store in stream_data by event type
                    if event_type not in STREAMING_STATE["stream_data"]:
                        STREAMING_STATE["stream_data"][event_type] = []

                    STREAMING_STATE["stream_data"][event_type].append({
                        "timestamp": datetime.now().isoformat(),
                        "data": events
                    })

                    # Keep only last 100 events per type
                    STREAMING_STATE["stream_data"][event_type] = \
                        STREAMING_STATE["stream_data"][event_type][-100:]

                    logger.debug(f"Received {event_type} data")

            elif data.get("type") == "AUTH_STATE":
                if data.get("state") == "AUTHORIZED":
                    logger.info("Successfully authorized with DXLink")
                elif data.get("state") == "UNAUTHORIZED":
                    logger.info("Need to authorize with DXLink")

        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
            break
        except Exception as e:
            logger.error(f"Error receiving message: {e}")


async def handle_subscribe_market_stream(arguments: dict[str, Any], websocket_manager=None) -> list[types.TextContent]:
    """Subscribe to market data streaming.

    Args:
        arguments: Dictionary containing:
            - symbols: Array of symbols to subscribe
            - events: Event types (default: Trade,Quote,Summary)

    Returns:
        List containing TextContent with subscription result
    """
    # Handle both array and string formats
    symbols_input = arguments.get("symbols", [])
    if isinstance(symbols_input, str):
        symbols = [s.strip().upper() for s in symbols_input.split(",")]
    elif isinstance(symbols_input, list):
        symbols = [s.strip().upper() for s in symbols_input]
    else:
        return [types.TextContent(type="text", text="Error: Symbols required (array or string)")]

    if not symbols:
        return [types.TextContent(type="text", text="Error: No symbols provided")]

    events_str = arguments.get("events", "Trade,Quote,Summary")
    events = [e.strip() for e in events_str.split(",")]

    try:
        # Get quote token if not already available
        if not STREAMING_STATE["quote_token"]:
            token_data = await get_quote_token()
            STREAMING_STATE["quote_token"] = token_data.get("token")
            STREAMING_STATE["dxlink_url"] = token_data.get("dxlink-url")
            logger.info(f"Got quote token, URL: {STREAMING_STATE['dxlink_url']}")

        # Connect WebSocket if not connected
        ws = STREAMING_STATE.get("websocket")
        if not ws or (hasattr(ws, 'closed') and ws.closed) or (hasattr(ws, 'state') and ws.state != websockets.protocol.State.OPEN):
            ws_url = STREAMING_STATE["dxlink_url"]
            STREAMING_STATE["websocket"] = await websockets.connect(ws_url)
            STREAMING_STATE["connected"] = True

            # Send SETUP
            await STREAMING_STATE["websocket"].send(json.dumps({
                "type": "SETUP",
                "channel": 0,
                "version": DXLINK_VERSION,
                "keepaliveTimeout": 60,
                "acceptKeepaliveTimeout": 60
            }))

            # Wait for AUTH_STATE
            await asyncio.sleep(0.5)

            # Send AUTH
            await STREAMING_STATE["websocket"].send(json.dumps({
                "type": "AUTH",
                "channel": 0,
                "token": STREAMING_STATE["quote_token"]
            }))

            # Open channel
            await STREAMING_STATE["websocket"].send(json.dumps({
                "type": "CHANNEL_REQUEST",
                "channel": STREAMING_STATE["channel"],
                "service": "FEED",
                "parameters": {"contract": "AUTO"}
            }))

            # Configure feed
            await STREAMING_STATE["websocket"].send(json.dumps({
                "type": "FEED_SETUP",
                "channel": STREAMING_STATE["channel"],
                "acceptAggregationPeriod": 0.1,
                "acceptDataFormat": "COMPACT",
                "acceptEventFields": {
                    "Trade": ["eventType", "eventSymbol", "price", "dayVolume", "size"],
                    "Quote": ["eventType", "eventSymbol", "bidPrice", "askPrice", "bidSize", "askSize"],
                    "Summary": ["eventType", "eventSymbol", "openInterest", "dayOpenPrice", "dayHighPrice", "dayLowPrice", "prevDayClosePrice"],
                    "Greeks": ["eventType", "eventSymbol", "volatility", "delta", "gamma", "theta", "rho", "vega"],
                    "Profile": ["eventType", "eventSymbol", "description", "shortSaleRestriction", "tradingStatus"]
                }
            }))

            # Start keepalive task
            if not STREAMING_STATE["keepalive_task"]:
                STREAMING_STATE["keepalive_task"] = asyncio.create_task(
                    send_keepalive(STREAMING_STATE["websocket"])
                )

            # Start receiver task
            if not STREAMING_STATE["receiver_task"]:
                STREAMING_STATE["receiver_task"] = asyncio.create_task(
                    receive_messages(STREAMING_STATE["websocket"])
                )

        # Build subscription message
        subscriptions = []
        for symbol in symbols:
            for event in events:
                subscriptions.append({"type": event, "symbol": symbol})

                # Track subscriptions
                if symbol not in STREAMING_STATE["subscriptions"]:
                    STREAMING_STATE["subscriptions"][symbol] = []
                if event not in STREAMING_STATE["subscriptions"][symbol]:
                    STREAMING_STATE["subscriptions"][symbol].append(event)

        # Send subscription
        await STREAMING_STATE["websocket"].send(json.dumps({
            "type": "FEED_SUBSCRIPTION",
            "channel": STREAMING_STATE["channel"],
            "reset": False,
            "add": subscriptions
        }))

        formatted = f"✅ Subscribed to streaming data\n"
        formatted += f"  Symbols: {', '.join(symbols)}\n"
        formatted += f"  Events: {', '.join(events)}\n"
        formatted += f"  Status: Connected to DXLink\n"
        formatted += f"  Active Subscriptions: {len(STREAMING_STATE['subscriptions'])}"

        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error subscribing to stream: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error subscribing to stream: {str(e)}"
        )]


async def handle_unsubscribe_market_stream(arguments: dict[str, Any], websocket_manager=None) -> list[types.TextContent]:
    """Unsubscribe from market data streaming.

    Args:
        arguments: Dictionary containing:
            - symbols: Array of symbols to unsubscribe
            - events: Event types to unsubscribe

    Returns:
        List containing TextContent with result
    """
    # Handle both array and string formats
    symbols_input = arguments.get("symbols", [])
    if isinstance(symbols_input, str):
        symbols = [s.strip().upper() for s in symbols_input.split(",")]
    elif isinstance(symbols_input, list):
        symbols = [s.strip().upper() for s in symbols_input]
    else:
        # If no symbols, unsubscribe all
        symbols = list(STREAMING_STATE["subscriptions"].keys()) if STREAMING_STATE["subscriptions"] else []
        if not symbols:
            return [types.TextContent(type="text", text="No active subscriptions to unsubscribe")]

    events_str = arguments.get("events", "Trade,Quote,Summary")
    events = [e.strip() for e in events_str.split(",")]

    try:
        ws = STREAMING_STATE.get("websocket")
        if not ws or (hasattr(ws, 'closed') and ws.closed) or (hasattr(ws, 'state') and ws.state != websockets.protocol.State.OPEN):
            return [types.TextContent(type="text", text="No active stream connection")]

        # Build unsubscribe message
        unsubscriptions = []
        for symbol in symbols:
            for event in events:
                unsubscriptions.append({"type": event, "symbol": symbol})

                # Remove from tracking
                if symbol in STREAMING_STATE["subscriptions"]:
                    if event in STREAMING_STATE["subscriptions"][symbol]:
                        STREAMING_STATE["subscriptions"][symbol].remove(event)
                    if not STREAMING_STATE["subscriptions"][symbol]:
                        del STREAMING_STATE["subscriptions"][symbol]

        # Send unsubscribe
        await STREAMING_STATE["websocket"].send(json.dumps({
            "type": "FEED_SUBSCRIPTION",
            "channel": STREAMING_STATE["channel"],
            "remove": unsubscriptions
        }))

        formatted = f"✅ Unsubscribed from streaming data\n"
        formatted += f"  Symbols: {', '.join(symbols)}\n"
        formatted += f"  Events: {', '.join(events)}\n"
        formatted += f"  Remaining Subscriptions: {len(STREAMING_STATE['subscriptions'])}"

        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error unsubscribing: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error unsubscribing: {str(e)}"
        )]


async def handle_get_stream_data(arguments: dict[str, Any], websocket_manager=None) -> list[types.TextContent]:
    """Get recent stream data.

    Args:
        arguments: Dictionary containing:
            - event_type: Type of events to retrieve
            - limit: Number of recent events (default 10)

    Returns:
        List containing TextContent with stream data
    """
    event_type = arguments.get("event_type", "Trade")
    limit = arguments.get("limit", 10)

    if event_type not in STREAMING_STATE["stream_data"]:
        return [types.TextContent(
            type="text",
            text=f"No data available for event type: {event_type}"
        )]

    events = STREAMING_STATE["stream_data"][event_type][-limit:]

    if not events:
        return [types.TextContent(type="text", text="No recent stream data")]

    formatted = f"📊 Recent {event_type} Events (Last {len(events)})\n\n"

    for event in events:
        formatted += f"[{event['timestamp']}]\n"
        formatted += f"  Data: {event['data']}\n\n"

    return [types.TextContent(type="text", text=formatted)]


async def handle_get_stream_status(arguments: dict[str, Any], websocket_manager=None) -> list[types.TextContent]:
    """Get streaming connection status."""

    # Check connection status properly
    ws = STREAMING_STATE.get("websocket")
    connected = False
    if ws:
        try:
            # Check if websocket has state attribute
            if hasattr(ws, 'state'):
                import websockets
                connected = ws.state == websockets.protocol.State.OPEN
            elif hasattr(ws, 'closed'):
                connected = not ws.closed
            else:
                connected = STREAMING_STATE.get("connected", False)
        except Exception:
            connected = False

    formatted = f"📡 STREAMING STATUS\n\n"
    formatted += f"Connected: {'🟢 YES' if connected else '🔴 NO'}\n"
    formatted += f"Quote Token: {'✅' if STREAMING_STATE['quote_token'] else '❌'}\n"
    formatted += f"Active Subscriptions: {len(STREAMING_STATE['subscriptions'])}\n"

    if STREAMING_STATE["subscriptions"]:
        formatted += "\nSubscriptions:\n"
        for symbol, events in STREAMING_STATE["subscriptions"].items():
            formatted += f"  {symbol}: {', '.join(events)}\n"

    if STREAMING_STATE["stream_data"]:
        formatted += "\nData Available:\n"
        for event_type, events in STREAMING_STATE["stream_data"].items():
            formatted += f"  {event_type}: {len(events)} events\n"

    return [types.TextContent(type="text", text=formatted)]


async def handle_get_stream_metrics(arguments: dict[str, Any], websocket_manager=None) -> list[types.TextContent]:
    """Get streaming metrics and statistics."""

    total_events = sum(len(events) for events in STREAMING_STATE["stream_data"].values())

    formatted = f"📈 STREAMING METRICS\n\n"
    formatted += f"Total Events Received: {total_events}\n"
    formatted += f"Event Types: {len(STREAMING_STATE['stream_data'])}\n"
    formatted += f"Active Subscriptions: {len(STREAMING_STATE['subscriptions'])}\n"

    if STREAMING_STATE["stream_data"]:
        formatted += "\nEvents by Type:\n"
        for event_type, events in STREAMING_STATE["stream_data"].items():
            formatted += f"  {event_type}: {len(events)} events\n"
            if events:
                latest = events[-1]
                formatted += f"    Latest: {latest['timestamp']}\n"

    return [types.TextContent(type="text", text=formatted)]


async def handle_shutdown_streams(arguments: dict[str, Any], websocket_manager=None) -> list[types.TextContent]:
    """Shutdown all streaming connections."""

    try:
        # Cancel tasks
        if STREAMING_STATE["keepalive_task"]:
            STREAMING_STATE["keepalive_task"].cancel()
            STREAMING_STATE["keepalive_task"] = None

        if STREAMING_STATE["receiver_task"]:
            STREAMING_STATE["receiver_task"].cancel()
            STREAMING_STATE["receiver_task"] = None

        # Close WebSocket
        ws = STREAMING_STATE["websocket"]
        if ws:
            try:
                # Check if it's a websockets connection
                if hasattr(ws, 'closed') and not ws.closed:
                    await ws.close()
                elif hasattr(ws, 'close'):
                    await ws.close()
            except Exception:
                pass  # Already closed

        # Reset state
        STREAMING_STATE["websocket"] = None
        STREAMING_STATE["connected"] = False
        STREAMING_STATE["subscriptions"] = {}
        STREAMING_STATE["stream_data"] = {}

        return [types.TextContent(
            type="text",
            text="✅ Streaming connections shut down successfully"
        )]

    except Exception as e:
        logger.error(f"Error shutting down streams: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error shutting down streams: {str(e)}"
        )]