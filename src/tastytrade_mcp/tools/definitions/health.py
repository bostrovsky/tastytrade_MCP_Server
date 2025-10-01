"""Health and system tool definitions."""
from typing import Any

import mcp.types as types


def get_health_tools() -> list[types.Tool]:
    """Get health and system monitoring tool definitions."""
    return [
        types.Tool(
            name="health_check",
            description="Check if the MCP server is running",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            },
        ),
    ]