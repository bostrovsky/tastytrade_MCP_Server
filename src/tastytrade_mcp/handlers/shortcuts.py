"""Shortcuts handler for managing and executing user-defined tool combinations."""
import json
import os
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime

import mcp.types as types

from tastytrade_mcp.handlers.registry import register_handler
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)

# Path to user shortcuts configuration
SHORTCUTS_FILE = Path(__file__).parent.parent / "config" / "user_shortcuts.json"


def load_shortcuts() -> Dict[str, Any]:
    """Load user shortcuts from config file."""
    if not SHORTCUTS_FILE.exists():
        logger.info("No shortcuts file found, creating default")
        default_shortcuts = {
            "morning_update": {
                "description": "Get morning portfolio status and market conditions",
                "tools": [
                    {"name": "get_accounts", "args": {"user_id": "{{user_id}}"}},
                    {"name": "get_balances", "args": {"user_id": "{{user_id}}", "account_number": "{{account_number}}"}},
                    {"name": "get_positions", "args": {"user_id": "{{user_id}}", "account_number": "{{account_number}}"}},
                    {"name": "scan_opportunities", "args": {"scan_type": "high_volume", "limit": 5}}
                ],
                "usage_count": 0,
                "last_used": None
            },
            "close_positions": {
                "description": "Close all positions and halt trading",
                "tools": [
                    {"name": "get_positions", "args": {"user_id": "{{user_id}}", "account_number": "{{account_number}}"}},
                    {"name": "emergency_exit", "args": {"user_id": "{{user_id}}", "account_number": "{{account_number}}"}},
                    {"name": "halt_trading", "args": {"user_id": "{{user_id}}", "account_number": "{{account_number}}"}}
                ],
                "usage_count": 0,
                "last_used": None
            }
        }
        save_shortcuts(default_shortcuts)
        return default_shortcuts

    try:
        with open(SHORTCUTS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load shortcuts: {e}")
        return {}


def save_shortcuts(shortcuts: Dict[str, Any]) -> bool:
    """Save shortcuts to config file with atomic write."""
    try:
        SHORTCUTS_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Write to temporary file first for atomic operation
        temp_file = SHORTCUTS_FILE.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(shortcuts, f, indent=2, default=str)

        # Atomic rename (replaces existing file)
        temp_file.replace(SHORTCUTS_FILE)

        # Verify the write was successful
        with open(SHORTCUTS_FILE, 'r') as f:
            saved_data = json.load(f)
            if saved_data == shortcuts:
                logger.info(f"Successfully saved shortcuts to {SHORTCUTS_FILE}")
                return True
            else:
                logger.error("Saved data doesn't match expected data")
                return False

    except Exception as e:
        logger.error(f"Failed to save shortcuts: {e}")
        # Clean up temp file if it exists
        if 'temp_file' in locals() and temp_file.exists():
            try:
                temp_file.unlink()
            except:
                pass
        return False


def substitute_variables(args: dict, context: dict) -> dict:
    """Substitute template variables in arguments."""
    result = {}
    for key, value in args.items():
        if isinstance(value, str) and "{{" in value:
            for var_name, var_value in context.items():
                value = value.replace(f"{{{{{var_name}}}}}", str(var_value))
        result[key] = value
    return result


@register_handler("list_shortcuts")
async def handle_list_shortcuts(arguments: dict[str, Any]) -> list[types.TextContent]:
    """List all available shortcuts."""
    shortcuts = load_shortcuts()

    if not shortcuts:
        return [types.TextContent(
            type="text",
            text="No shortcuts defined. Use `create_shortcut` to create one."
        )]

    output = f"# Available Shortcuts ({len(shortcuts)} total)\n\n"

    for name, config in shortcuts.items():
        desc = config.get("description", "No description")
        tools_count = len(config.get("tools", []))
        usage = config.get("usage_count", 0)
        last_used = config.get("last_used", "Never")

        output += f"## {name}\n"
        output += f"**Description:** {desc}\n"
        output += f"**Tools:** {tools_count} tools in sequence\n"
        output += f"**Usage:** {usage} times\n"
        output += f"**Last Used:** {last_used}\n\n"

    output += "\nUse `execute_shortcut` with shortcut_name to run."

    return [types.TextContent(type="text", text=output)]


@register_handler("create_shortcut")
async def handle_create_shortcut(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Create a new shortcut."""
    name = arguments.get("name")
    description = arguments.get("description", "Custom shortcut")
    tools = arguments.get("tools", [])

    if not name:
        return [types.TextContent(
            type="text",
            text="Error: Shortcut name is required"
        )]

    if not tools:
        return [types.TextContent(
            type="text",
            text="Error: At least one tool must be specified"
        )]

    shortcuts = load_shortcuts()

    if name in shortcuts:
        return [types.TextContent(
            type="text",
            text=f"Error: Shortcut '{name}' already exists. Delete it first or choose another name."
        )]

    shortcuts[name] = {
        "description": description,
        "tools": tools,
        "usage_count": 0,
        "last_used": None,
        "created_at": datetime.utcnow().isoformat()
    }

    if save_shortcuts(shortcuts):
        output = f"✅ Shortcut '{name}' created successfully!\n\n"
        output += f"**Description:** {description}\n"
        output += f"**Tools:** {len(tools)} tools configured\n\n"
        output += "Run with: `execute_shortcut` shortcut_name=\"" + name + "\""

        return [types.TextContent(type="text", text=output)]
    else:
        return [types.TextContent(
            type="text",
            text=f"Error: Failed to save shortcut '{name}'"
        )]


@register_handler("execute_shortcut")
async def handle_execute_shortcut(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Execute a shortcut."""
    shortcut_name = arguments.get("shortcut_name")
    user_id = arguments.get("user_id")
    account_number = arguments.get("account_number")

    if not shortcut_name:
        return [types.TextContent(
            type="text",
            text="Error: shortcut_name is required"
        )]

    if not user_id:
        return [types.TextContent(
            type="text",
            text="Error: user_id is required for authentication"
        )]

    shortcuts = load_shortcuts()

    if shortcut_name not in shortcuts:
        return [types.TextContent(
            type="text",
            text=f"Error: Shortcut '{shortcut_name}' not found. Use `list_shortcuts` to see available shortcuts."
        )]

    shortcut = shortcuts[shortcut_name]
    tools = shortcut.get("tools", [])

    # Update usage statistics
    shortcut["usage_count"] = shortcut.get("usage_count", 0) + 1
    shortcut["last_used"] = datetime.utcnow().isoformat()
    save_shortcuts(shortcuts)

    # Execute tools
    context = {
        "user_id": user_id,
        "account_number": account_number or "",
        "today": datetime.utcnow().strftime("%Y-%m-%d")
    }

    output = f"# Executing Shortcut: {shortcut_name}\n\n"
    output += f"{shortcut.get('description', '')}\n\n"
    output += "---\n\n"

    # Import handlers dynamically
    from tastytrade_mcp.handlers import registry

    for i, tool_config in enumerate(tools, 1):
        tool_name = tool_config.get("name")
        tool_args = substitute_variables(tool_config.get("args", {}), context)

        output += f"## Step {i}: {tool_name}\n\n"

        try:
            handler = registry.get_handler(tool_name)
            if handler:
                result = await handler(tool_args)
                if result and isinstance(result, list):
                    for content in result:
                        if hasattr(content, 'text'):
                            output += content.text + "\n\n"
                        else:
                            output += str(content) + "\n\n"
                else:
                    output += f"Tool completed successfully\n\n"
            else:
                output += f"⚠️ Tool '{tool_name}' not found\n\n"
        except Exception as e:
            output += f"❌ Error executing {tool_name}: {str(e)}\n\n"

        output += "---\n\n"

    output += f"✅ Shortcut '{shortcut_name}' execution complete!"

    return [types.TextContent(type="text", text=output)]


@register_handler("test_shortcut")
async def handle_test_shortcut(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Test a shortcut without updating usage stats."""
    shortcut_name = arguments.get("shortcut_name")
    user_id = arguments.get("user_id")
    account_number = arguments.get("account_number")

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

    shortcut = shortcuts[shortcut_name]
    tools = shortcut.get("tools", [])

    output = f"# TEST MODE: {shortcut_name}\n\n"
    output += f"**Description:** {shortcut.get('description', '')}\n\n"
    output += "## Tools to be executed:\n\n"

    context = {
        "user_id": user_id or "{{user_id}}",
        "account_number": account_number or "{{account_number}}",
        "today": datetime.utcnow().strftime("%Y-%m-%d")
    }

    for i, tool_config in enumerate(tools, 1):
        tool_name = tool_config.get("name")
        tool_args = substitute_variables(tool_config.get("args", {}), context)

        output += f"{i}. **{tool_name}**\n"
        output += f"   Args: {json.dumps(tool_args, indent=2)}\n\n"

    output += "\n✅ Test complete. Use `execute_shortcut` to run for real."

    return [types.TextContent(type="text", text=output)]


@register_handler("delete_shortcut")
async def handle_delete_shortcut(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Delete a shortcut."""
    name = arguments.get("name")
    confirm = arguments.get("confirm", False)

    if not name:
        return [types.TextContent(
            type="text",
            text="Error: Shortcut name is required"
        )]

    # Load current shortcuts
    shortcuts = load_shortcuts()

    if name not in shortcuts:
        return [types.TextContent(
            type="text",
            text=f"Error: Shortcut '{name}' not found.\n\n"
            f"Available shortcuts: {', '.join(shortcuts.keys()) if shortcuts else 'None'}"
        )]

    # Don't allow deleting built-in shortcuts without confirmation
    if name in ["morning_update", "close_positions"]:
        if not confirm:
            return [types.TextContent(
                type="text",
                text=f"⚠️ Warning: '{name}' is a built-in shortcut.\n\n"
                f"To delete it anyway, use confirm=true"
            )]

    # Store the shortcut details before deletion for confirmation
    deleted_shortcut = shortcuts[name]
    description = deleted_shortcut.get('description', 'No description')
    tools_count = len(deleted_shortcut.get('tools', []))
    usage_count = deleted_shortcut.get('usage_count', 0)

    # Delete the shortcut
    del shortcuts[name]

    # Save the updated shortcuts
    if save_shortcuts(shortcuts):
        # Verify deletion by reloading
        reloaded = load_shortcuts()
        if name not in reloaded:
            return [types.TextContent(
                type="text",
                text=f"✅ Shortcut '{name}' deleted successfully!\n\n"
                f"**Deleted shortcut details:**\n"
                f"• Description: {description}\n"
                f"• Tools: {tools_count}\n"
                f"• Usage count: {usage_count}\n\n"
                f"Remaining shortcuts: {', '.join(reloaded.keys()) if reloaded else 'None'}"
            )]
        else:
            return [types.TextContent(
                type="text",
                text=f"⚠️ Deletion may have partially failed.\n"
                f"Shortcut '{name}' still appears to exist.\n"
                f"Please try again or check file permissions."
            )]
    else:
        return [types.TextContent(
            type="text",
            text=f"❌ Error: Failed to delete shortcut '{name}'.\n"
            f"The shortcuts file could not be updated.\n"
            f"Check file permissions at: {SHORTCUTS_FILE}"
        )]