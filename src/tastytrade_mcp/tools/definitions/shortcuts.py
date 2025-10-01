"""Shortcuts management tool definitions."""
from typing import Any

import mcp.types as types


def get_shortcuts_tools() -> list[types.Tool]:
    """Get shortcuts management tool definitions."""
    return [
        types.Tool(
            name="list_shortcuts",
            description="List all available user-defined shortcuts with their descriptions and usage statistics",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="execute_shortcut",
            description="Execute a saved shortcut by name, running all its configured tools in sequence and aggregating results",
            inputSchema={
                "type": "object",
                "properties": {
                    "shortcut_name": {
                        "type": "string",
                        "description": "Name of the shortcut to execute"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID (required for tools that need authentication)"
                    },
                    "account_number": {
                        "type": "string",
                        "description": "Account number (used by tools that need account context)"
                    }
                },
                "required": ["shortcut_name", "user_id"]
            }
        ),
        types.Tool(
            name="test_shortcut",
            description="Test a shortcut by executing all its tools and showing a preview without updating usage statistics. Use this before running a new shortcut to verify it works correctly.",
            inputSchema={
                "type": "object",
                "properties": {
                    "shortcut_name": {
                        "type": "string",
                        "description": "Name of the shortcut to test"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID (required for tools that need authentication)"
                    },
                    "account_number": {
                        "type": "string",
                        "description": "Account number (used by tools that need account context)"
                    }
                },
                "required": ["shortcut_name", "user_id"]
            }
        ),
        types.Tool(
            name="create_shortcut",
            description="Create a new shortcut that combines multiple tool calls into a single command",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Unique name for the shortcut (e.g., 'morning_update', 'last_call')"
                    },
                    "description": {
                        "type": "string",
                        "description": "Human-readable description of what this shortcut does"
                    },
                    "tools": {
                        "type": "array",
                        "description": "List of tools to execute in sequence",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Tool name to execute"
                                },
                                "args": {
                                    "type": "object",
                                    "description": "Arguments for the tool. Use {{user_id}}, {{account_number}}, {{today}} for template variables"
                                }
                            },
                            "required": ["name", "args"]
                        }
                    }
                },
                "required": ["name", "tools"]
            }
        ),
        types.Tool(
            name="delete_shortcut",
            description="Delete an existing shortcut by name",
            inputSchema={
                "type": "object",
                "properties": {
                    "shortcut_name": {
                        "type": "string",
                        "description": "Name of the shortcut to delete"
                    }
                },
                "required": ["shortcut_name"]
            }
        )
    ]