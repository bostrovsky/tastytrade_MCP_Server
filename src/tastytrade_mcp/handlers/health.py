"""Health check handler for TastyTrade MCP."""
from typing import Any
import mcp.types as types
import logging

logger = logging.getLogger(__name__)


async def handle_health_check(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handle health check request."""
    try:
        return [types.TextContent(text="Service is healthy", type="text")]
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return [types.TextContent(text=f"Health check failed: {str(e)}", type="text")]