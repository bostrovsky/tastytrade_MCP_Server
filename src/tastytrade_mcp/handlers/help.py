"""Help handler for listing and explaining available MCP tools."""
from typing import Any

import mcp.types as types

from tastytrade_mcp.handlers.registry import register_handler
from tastytrade_mcp.tools.definitions.all_tools import get_all_tools
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)

TOOL_CATEGORIES = {
    "account": {
        "icon": "📊",
        "title": "ACCOUNT MANAGEMENT",
        "tools": ["get_accounts", "get_balances", "get_positions"]
    },
    "market_data": {
        "icon": "📈",
        "title": "MARKET DATA",
        "tools": ["search_symbols", "search_symbols_advanced", "get_quotes",
                 "get_historical_data", "get_options_chain", "scan_opportunities"]
    },
    "trading": {
        "icon": "💼",
        "title": "TRADING & ORDERS",
        "tools": ["create_equity_order", "create_options_order", "confirm_order",
                 "cancel_order", "list_orders", "set_stop_loss", "set_take_profit"]
    },
    "positions": {
        "icon": "🎯",
        "title": "POSITION ANALYSIS",
        "tools": ["get_positions_with_greeks", "analyze_portfolio", "monitor_position_alerts",
                 "analyze_position_correlation", "bulk_position_update", "analyze_options_strategy",
                 "suggest_rebalancing"]
    },
    "emergency": {
        "icon": "🚨",
        "title": "EMERGENCY CONTROLS",
        "tools": ["panic_button", "emergency_exit", "halt_trading", "resume_trading",
                 "emergency_stop_all", "create_circuit_breaker", "check_emergency_conditions",
                 "get_emergency_history"]
    },
    "streaming": {
        "icon": "🔍",
        "title": "SCANNING & STREAMING",
        "tools": ["subscribe_market_stream", "unsubscribe_market_stream", "get_stream_data",
                 "get_stream_status", "get_stream_metrics", "shutdown_streams"]
    },
    "shortcuts": {
        "icon": "🔧",
        "title": "SHORTCUTS & AUTOMATION",
        "tools": ["list_shortcuts", "create_shortcut", "execute_shortcut",
                 "test_shortcut", "delete_shortcut"]
    },
    "health": {
        "icon": "🏥",
        "title": "SYSTEM HEALTH",
        "tools": ["health_check", "ping"]
    }
}


def get_tool_by_name(tool_name: str) -> types.Tool | None:
    """Find a tool definition by name."""
    all_tools = get_all_tools()
    for tool in all_tools:
        if tool.name == tool_name:
            return tool
    return None


def format_parameter(name: str, schema: dict) -> str:
    """Format a parameter for display."""
    param_type = schema.get("type", "unknown")
    required = " (required)" if name in schema.get("required", []) else " (optional)"
    description = schema.get("description", "No description")

    return f"**{name}**{required}\n  Type: {param_type}\n  {description}"


def format_detailed_help(tool: types.Tool) -> str:
    """Format detailed help for a specific tool."""
    category_name = "Other"
    category_icon = "📦"

    for cat_key, cat_data in TOOL_CATEGORIES.items():
        if tool.name in cat_data["tools"]:
            category_name = cat_data["title"]
            category_icon = cat_data["icon"]
            break

    output = f"# Tool: {tool.name}\n\n"
    output += f"**Category:** {category_icon} {category_name}\n\n"
    output += f"**Description:**\n{tool.description}\n\n"
    output += "---\n\n"

    if tool.inputSchema and "properties" in tool.inputSchema:
        output += "## PARAMETERS\n\n"
        props = tool.inputSchema["properties"]
        required = tool.inputSchema.get("required", [])

        for param_name, param_schema in props.items():
            param_type = param_schema.get("type", "unknown")
            param_desc = param_schema.get("description", "No description")
            is_required = " (required)" if param_name in required else " (optional)"

            output += f"**{param_name}**{is_required}\n"
            output += f"  Type: {param_type}\n"
            output += f"  {param_desc}\n\n"

        output += "---\n\n"

    output += "Type `help` (without tool name) to see all available tools.\n"

    return output


def format_general_help() -> str:
    """Format general help showing all tools by category."""
    output = "# TastyTrade MCP Server - Help Guide\n\n"

    all_tools = get_all_tools()
    output += f"Welcome! You have access to **{len(all_tools)} tools** across **{len(TOOL_CATEGORIES)} categories**.\n\n"
    output += "---\n\n"

    for category_key, category_data in TOOL_CATEGORIES.items():
        icon = category_data["icon"]
        title = category_data["title"]
        tools = category_data["tools"]

        output += f"## {icon} {title} ({len(tools)} tools)\n\n"

        for tool_name in tools:
            tool = get_tool_by_name(tool_name)
            if tool:
                desc = tool.description
                if len(desc) > 80:
                    desc = desc[:77] + "..."
                output += f"• **{tool_name}** - {desc}\n"

        output += "\n---\n\n"

    try:
        from tastytrade_mcp.handlers.composite.shortcuts import load_shortcuts
        shortcuts = load_shortcuts()
        if shortcuts:
            output += "## 📚 PRE-BUILT SHORTCUTS\n\n"
            output += f"You have {len(shortcuts)} shortcuts ready to use:\n\n"

            for name, config in shortcuts.items():
                desc = config.get("description", "No description")
                output += f"• **{name}** - {desc}\n"

            output += "\nRun with: `execute_shortcut` with shortcut_name parameter\n\n"
            output += "---\n\n"
    except Exception as e:
        logger.warning(f"Could not load shortcuts: {e}")

    output += "## 💡 QUICK START\n\n"
    output += "**View your accounts:**\n"
    output += "  Call `get_accounts` with your user_id\n\n"
    output += "**Check morning portfolio:**\n"
    output += "  Call `execute_shortcut` with shortcut_name=\"morning_update\"\n\n"
    output += "**Get help on specific tool:**\n"
    output += "  Call `help` with tool_name=\"create_shortcut\"\n\n"
    output += "**Create your own routine:**\n"
    output += "  Use `create_shortcut` to combine tools you use frequently\n\n"
    output += "---\n\n"
    output += "Type `help` with a tool_name parameter for detailed information about that tool.\n"

    return output


@register_handler("help")
async def handle_help(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Provide help information about available tools."""
    tool_name = arguments.get("tool_name")

    if tool_name:
        logger.info(f"Providing detailed help for tool: {tool_name}")
        tool = get_tool_by_name(tool_name)

        if not tool:
            return [types.TextContent(
                type="text",
                text=f"Tool '{tool_name}' not found.\n\nUse `help` (without tool_name) to see all available tools."
            )]

        help_text = format_detailed_help(tool)
        return [types.TextContent(type="text", text=help_text)]
    else:
        logger.info("Providing general help (all tools)")
        help_text = format_general_help()
        return [types.TextContent(type="text", text=help_text)]