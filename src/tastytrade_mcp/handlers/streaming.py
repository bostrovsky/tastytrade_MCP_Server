"""Streaming data handlers for TastyTrade MCP."""
import json
from typing import Any

import mcp.types as types

from tastytrade_mcp.handlers.handler_adapter import HandlerAdapter
from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()
adapter = HandlerAdapter(use_database=settings.use_database_mode)


async def handle_subscribe_market_stream(arguments: dict[str, Any], websocket_manager) -> list[types.TextContent]:
    """Subscribe to real-time market data streams.

    Args:
        arguments: Dictionary containing:
            - symbols: List of symbols to subscribe to (required)
            - data_types: Types of data to stream (default: ["quote", "trade"])
            - user_id: User ID for the subscription
            - session_id: Session ID for the subscription
        websocket_manager: WebSocket manager instance

    Returns:
        List containing TextContent with subscription result
    """
    try:
        symbols = arguments.get("symbols", [])
        if not symbols:
            return [types.TextContent(type="text", text="Error: symbols parameter is required")]

        data_types = arguments.get("data_types", ["quote", "trade"])
        user_id = arguments.get("user_id", "default")
        session_id = arguments.get("session_id")

        # In future implementations, may need session for WebSocket authentication
        # session = await adapter.get_session(user_id)

        # For now, WebSocketManager operates independently of TastyTrade sessions
        # as it's currently a mock implementation that generates simulated data
        result = await websocket_manager.subscribe(
            symbols=symbols,
            data_types=data_types,
            user_id=user_id,
            session_id=session_id
        )

        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    except ValueError as e:
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
    except Exception as e:
        logger.error(f"Error subscribing to market stream: {e}", exc_info=True)
        return [types.TextContent(type="text", text=json.dumps({"error": f"Streaming error: {str(e)}"}, indent=2))]


async def handle_unsubscribe_market_stream(arguments: dict[str, Any], websocket_manager) -> list[types.TextContent]:
    """Unsubscribe from real-time market data streams.

    Args:
        arguments: Dictionary containing:
            - symbols: List of symbols to unsubscribe from
            - user_id: User ID for the subscription
            - session_id: Session ID for the subscription
        websocket_manager: WebSocket manager instance

    Returns:
        List containing TextContent with unsubscription result
    """
    try:
        symbols = arguments.get("symbols")
        user_id = arguments.get("user_id", "default")
        session_id = arguments.get("session_id")

        # In future implementations, may need session for WebSocket authentication
        # session = await adapter.get_session(user_id)

        # For now, WebSocketManager operates independently of TastyTrade sessions
        result = await websocket_manager.unsubscribe(
            symbols=symbols,
            user_id=user_id,
            session_id=session_id
        )

        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Error unsubscribing from market stream: {e}", exc_info=True)
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]


async def handle_get_stream_data(arguments: dict[str, Any], websocket_manager) -> list[types.TextContent]:
    """Get latest data from active streams.

    Args:
        arguments: Dictionary containing:
            - symbols: List of symbols to get data for (required)
            - data_type: Type of data to retrieve (default: "latest")
            - user_id: User ID for data access
        websocket_manager: WebSocket manager instance

    Returns:
        List containing TextContent with stream data
    """
    try:
        symbols = arguments.get("symbols", [])

        # Handle symbols as string (convert to list)
        if isinstance(symbols, str):
            symbols = [s.strip() for s in symbols.split(",") if s.strip()]

        if not symbols:
            return [types.TextContent(type="text", text="Error: symbols parameter is required")]

        data_type = arguments.get("data_type", "latest")
        user_id = arguments.get("user_id", "default")

        # In future implementations, may need session for data access authorization
        # session = await adapter.get_session(user_id)

        # For now, WebSocketManager provides mock data without authentication
        data = await websocket_manager.get_latest_data(symbols, data_type)
        result = {"data": data}

        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Error getting stream data: {e}", exc_info=True)
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]


async def handle_get_stream_status(arguments: dict[str, Any], websocket_manager) -> list[types.TextContent]:
    """Get status of active streams.

    Args:
        arguments: Dictionary containing:
            - user_id: User ID for status access
        websocket_manager: WebSocket manager instance

    Returns:
        List containing TextContent with stream status
    """
    try:
        user_id = arguments.get("user_id", "default")

        # In future implementations, may need session for status access authorization
        # session = await adapter.get_session(user_id)

        # For now, WebSocketManager provides status without authentication
        result = await websocket_manager.get_status()
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Error getting stream status: {e}", exc_info=True)
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]


async def handle_get_stream_metrics(arguments: dict[str, Any], websocket_manager) -> list[types.TextContent]:
    """Get performance metrics for active streams.

    Args:
        arguments: Dictionary containing:
            - user_id: User ID for metrics access
        websocket_manager: WebSocket manager instance

    Returns:
        List containing TextContent with stream metrics
    """
    try:
        user_id = arguments.get("user_id", "default")

        # In future implementations, may need session for metrics access authorization
        # session = await adapter.get_session(user_id)

        # For now, WebSocketManager provides metrics without authentication
        result = await websocket_manager.get_metrics()
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Error getting stream metrics: {e}", exc_info=True)
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]


async def handle_shutdown_streams(arguments: dict[str, Any], websocket_manager) -> list[types.TextContent]:
    """Shutdown all active streams.

    Args:
        arguments: Dictionary containing:
            - user_id: User ID for shutdown authorization
        websocket_manager: WebSocket manager instance

    Returns:
        List containing TextContent with shutdown result
    """
    try:
        user_id = arguments.get("user_id", "default")

        # In future implementations, may need session for shutdown authorization
        # session = await adapter.get_session(user_id)

        # For now, WebSocketManager allows shutdown without authentication
        result = await websocket_manager.shutdown()
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

    except Exception as e:
        logger.error(f"Error shutting down streams: {e}", exc_info=True)
        return [types.TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]