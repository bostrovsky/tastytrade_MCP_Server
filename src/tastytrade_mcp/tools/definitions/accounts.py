"""Account-related tool definitions."""
from typing import Any

import mcp.types as types


def get_account_tools() -> list[types.Tool]:
    """Get account management tool definitions."""
    return [
        types.Tool(
            name="get_accounts",
            description="Get all linked TastyTrade accounts for a user",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID to get accounts for"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["text", "json"],
                        "description": "Output format (default: text)",
                        "default": "text"
                    }
                },
                "required": ["user_id"]
            },
        ),
        types.Tool(
            name="get_positions",
            description="Get all positions for a specific account",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID who owns the account"
                    },
                    "account_number": {
                        "type": "string",
                        "description": "Account number to get positions for"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["text", "json"],
                        "description": "Output format (default: text)",
                        "default": "text"
                    }
                },
                "required": ["user_id", "account_number"]
            },
        ),
        types.Tool(
            name="get_positions_with_greeks",
            description="Get all positions with Greek data for options analysis",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID who owns the account"
                    },
                    "account_number": {
                        "type": "string",
                        "description": "Account number to get positions for"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["text", "json"],
                        "description": "Output format (default: text)",
                        "default": "text"
                    }
                },
                "required": ["user_id", "account_number"]
            },
        ),
        types.Tool(
            name="analyze_portfolio",
            description="Comprehensive portfolio analysis including Greeks aggregation, risk metrics, and asset allocation",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID who owns the account"
                    },
                    "account_number": {
                        "type": "string",
                        "description": "Account number to analyze"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["text", "json"],
                        "description": "Output format (default: text)",
                        "default": "text"
                    }
                },
                "required": ["user_id", "account_number"]
            },
        ),
        types.Tool(
            name="get_balances",
            description="Get balance information for a specific account",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID who owns the account"
                    },
                    "account_number": {
                        "type": "string",
                        "description": "Account number to get balances for"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["text", "json"],
                        "description": "Output format (default: text)",
                        "default": "text"
                    }
                },
                "required": ["user_id", "account_number"]
            },
        ),
    ]