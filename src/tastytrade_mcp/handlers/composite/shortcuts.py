"""Composite shortcuts handler for managing user-defined tool combinations."""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import mcp.types as types

from tastytrade_mcp.handlers.registry import dispatch, register_handler
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)

SHORTCUTS_FILE = Path(__file__).parent.parent.parent / "config" / "user_shortcuts.json"


def load_shortcuts() -> dict[str, Any]:
    """Load shortcuts from JSON file."""
    try:
        if not SHORTCUTS_FILE.exists():
            return {}
        with open(SHORTCUTS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading shortcuts: {e}")
        return {}


def save_shortcuts(shortcuts: dict[str, Any]) -> None:
    """Save shortcuts to JSON file."""
    try:
        SHORTCUTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SHORTCUTS_FILE, "w") as f:
            json.dump(shortcuts, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving shortcuts: {e}")
        raise


def replace_variables(args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Replace template variables in arguments."""
    result = {}
    for key, value in args.items():
        if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
            var_name = value[2:-2].strip()
            if var_name == "today":
                result[key] = datetime.now().strftime("%Y-%m-%d")
            elif var_name in context:
                result[key] = context[var_name]
            else:
                result[key] = value
        else:
            result[key] = value
    return result


@register_handler("list_shortcuts")
async def handle_list_shortcuts(arguments: dict[str, Any]) -> list[types.TextContent]:
    """List all available shortcuts."""
    shortcuts = load_shortcuts()

    if not shortcuts:
        return [types.TextContent(
            type="text",
            text="No shortcuts defined yet. Use 'create_shortcut' to create your first one!"
        )]

    output = "📋 Available Shortcuts:\n\n"
    for name, config in shortcuts.items():
        output += f"**{name}**\n"
        output += f"  Description: {config.get('description', 'No description')}\n"
        output += f"  Tools: {len(config.get('tools', []))} tool(s)\n"
        output += f"  Times used: {config.get('execution_count', 0)}\n"
        if config.get('last_used'):
            output += f"  Last used: {config['last_used']}\n"
        output += "\n"

    return [types.TextContent(type="text", text=output)]


@register_handler("execute_shortcut")
async def handle_execute_shortcut(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Execute a saved shortcut."""
    shortcut_name = arguments.get("shortcut_name")
    user_id = arguments.get("user_id")
    account_number = arguments.get("account_number")

    if not shortcut_name:
        return [types.TextContent(
            type="text",
            text="Error: shortcut_name is required"
        )]

    shortcuts = load_shortcuts()
    shortcut = shortcuts.get(shortcut_name)

    if not shortcut:
        available = ", ".join(shortcuts.keys()) if shortcuts else "none"
        return [types.TextContent(
            type="text",
            text=f"Error: Shortcut '{shortcut_name}' not found. Available shortcuts: {available}"
        )]

    context = {
        "user_id": user_id,
        "account_number": account_number
    }

    logger.info(f"Executing shortcut '{shortcut_name}' with {len(shortcut['tools'])} tools")

    results = []
    errors = []

    for i, tool_config in enumerate(shortcut["tools"]):
        tool_name = tool_config["name"]
        tool_args = replace_variables(tool_config["args"], context)

        try:
            logger.info(f"  Executing tool {i+1}/{len(shortcut['tools'])}: {tool_name}")
            result = await dispatch(tool_name, tool_args)
            results.append({
                "tool": tool_name,
                "result": result,
                "success": True
            })
        except Exception as e:
            logger.error(f"  Error executing {tool_name}: {e}")
            errors.append({
                "tool": tool_name,
                "error": str(e)
            })
            results.append({
                "tool": tool_name,
                "result": None,
                "success": False,
                "error": str(e)
            })

    shortcut["execution_count"] = shortcut.get("execution_count", 0) + 1
    shortcut["last_used"] = datetime.now().isoformat()
    shortcuts[shortcut_name] = shortcut
    save_shortcuts(shortcuts)

    output = f"# {shortcut_name.replace('_', ' ').title()}\n"
    output += f"_{shortcut.get('description', 'No description')}_\n\n"
    output += "---\n\n"

    for item in results:
        if item["success"]:
            output += f"## {item['tool']}\n"
            for content in item["result"]:
                if hasattr(content, 'text'):
                    output += content.text + "\n\n"
        else:
            output += f"## {item['tool']} ❌\n"
            output += f"Error: {item.get('error', 'Unknown error')}\n\n"

    if errors:
        output += f"\n⚠️ {len(errors)} tool(s) failed during execution\n"

    return [types.TextContent(type="text", text=output)]


@register_handler("test_shortcut")
async def handle_test_shortcut(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Test a shortcut without saving usage stats."""
    shortcut_name = arguments.get("shortcut_name")
    user_id = arguments.get("user_id")
    account_number = arguments.get("account_number")

    if not shortcut_name:
        return [types.TextContent(
            type="text",
            text="Error: shortcut_name is required"
        )]

    shortcuts = load_shortcuts()
    shortcut = shortcuts.get(shortcut_name)

    if not shortcut:
        return [types.TextContent(
            type="text",
            text=f"Error: Shortcut '{shortcut_name}' not found"
        )]

    context = {
        "user_id": user_id,
        "account_number": account_number
    }

    logger.info(f"Testing shortcut '{shortcut_name}'")

    start_time = datetime.now()
    test_results = {
        "success": [],
        "failures": [],
        "execution_time": 0
    }

    for i, tool_config in enumerate(shortcut["tools"]):
        tool_name = tool_config["name"]
        tool_args = replace_variables(tool_config["args"], context)

        try:
            result = await dispatch(tool_name, tool_args)

            data_summary = "Success"
            if result and len(result) > 0 and hasattr(result[0], 'text'):
                text = result[0].text
                if len(text) > 100:
                    data_summary = f"{text[:100]}..."
                else:
                    data_summary = text

            test_results["success"].append({
                "tool": tool_name,
                "status": "✓ Success",
                "summary": data_summary
            })
        except Exception as e:
            test_results["failures"].append({
                "tool": tool_name,
                "error": str(e)
            })

    end_time = datetime.now()
    test_results["execution_time"] = (end_time - start_time).total_seconds()

    output = f"# Test Results: {shortcut_name}\n\n"
    output += f"**Description:** {shortcut.get('description', 'No description')}\n"
    output += f"**Execution time:** {test_results['execution_time']:.2f}s\n\n"

    if test_results["success"]:
        output += "## ✓ Successful Tools\n\n"
        for item in test_results["success"]:
            output += f"- **{item['tool']}**: {item['summary']}\n"
        output += "\n"

    if test_results["failures"]:
        output += "## ❌ Failed Tools\n\n"
        for item in test_results["failures"]:
            output += f"- **{item['tool']}**: {item['error']}\n"
        output += "\n"

    if not test_results["failures"]:
        output += "\n✅ **All tools executed successfully!**\n"
        output += "This shortcut is ready to use with `execute_shortcut`.\n"
    else:
        output += f"\n⚠️ **{len(test_results['failures'])} tool(s) failed.**\n"
        output += "Please fix the errors before using this shortcut.\n"

    return [types.TextContent(type="text", text=output)]


@register_handler("create_shortcut")
async def handle_create_shortcut(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Create a new shortcut."""
    name = arguments.get("name")
    description = arguments.get("description", "")
    tools = arguments.get("tools", [])

    if not name:
        return [types.TextContent(
            type="text",
            text="Error: name is required"
        )]

    if not tools:
        return [types.TextContent(
            type="text",
            text="Error: tools list is required (must include at least one tool)"
        )]

    shortcuts = load_shortcuts()

    if name in shortcuts:
        return [types.TextContent(
            type="text",
            text=f"Error: Shortcut '{name}' already exists. Use a different name or delete the existing one first."
        )]

    shortcuts[name] = {
        "description": description,
        "tools": tools,
        "format": "summary",
        "created": datetime.now().isoformat(),
        "last_used": None,
        "execution_count": 0
    }

    try:
        save_shortcuts(shortcuts)
        output = f"✅ Created shortcut '{name}'\n\n"
        output += f"**Description:** {description}\n"
        output += f"**Tools:** {len(tools)} tool(s)\n\n"
        output += "You can now:\n"
        output += f"- Test it: `test_shortcut` with shortcut_name='{name}'\n"
        output += f"- Run it: `execute_shortcut` with shortcut_name='{name}'\n"
        output += f"- Delete it: `delete_shortcut` with shortcut_name='{name}'\n"

        return [types.TextContent(type="text", text=output)]
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"Error saving shortcut: {str(e)}"
        )]


@register_handler("delete_shortcut")
async def handle_delete_shortcut(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Delete a shortcut."""
    shortcut_name = arguments.get("shortcut_name")

    if not shortcut_name:
        return [types.TextContent(
            type="text",
            text="Error: shortcut_name is required"
        )]

    shortcuts = load_shortcuts()

    if shortcut_name not in shortcuts:
        return [types.TextContent(
            type="text",
            text=f"Error: Shortcut '{shortcut_name}' not found"
        )]

    del shortcuts[shortcut_name]

    try:
        save_shortcuts(shortcuts)
        return [types.TextContent(
            type="text",
            text=f"✅ Deleted shortcut '{shortcut_name}'"
        )]
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"Error deleting shortcut: {str(e)}"
        )]