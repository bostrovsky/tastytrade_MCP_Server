"""Help tool definition."""
import mcp.types as types


def get_help_tools() -> list[types.Tool]:
    """Get help tool definitions."""
    return [
        types.Tool(
            name="help",
            description="Get help and documentation for available MCP tools. Call without parameters to see all tools, or with tool_name to get detailed help for a specific tool.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Optional: Name of specific tool to get detailed help for (e.g., 'create_shortcut', 'get_accounts')"
                    }
                },
                "required": []
            }
        )
    ]