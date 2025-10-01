"""Trading tool definitions."""
from typing import Any

import mcp.types as types


def get_trading_tools() -> list[types.Tool]:
    """Get basic trading tool definitions."""
    return [
        types.Tool(
            name="create_equity_order",
            description="Create a preview for an equity order (requires confirmation)",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID who owns the account"
                    },
                    "account_number": {
                        "type": "string",
                        "description": "Account number to place the order"
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Trading symbol"
                    },
                    "side": {
                        "type": "string",
                        "enum": ["buy", "sell"],
                        "description": "Order side"
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of shares",
                        "minimum": 1,
                        "maximum": 10000
                    },
                    "order_type": {
                        "type": "string",
                        "enum": ["market", "limit", "stop", "stop_limit"],
                        "description": "Order type"
                    },
                    "price": {
                        "type": "number",
                        "description": "Limit price (required for limit/stop_limit orders)"
                    },
                    "stop_price": {
                        "type": "number",
                        "description": "Stop price (required for stop/stop_limit orders)"
                    },
                    "time_in_force": {
                        "type": "string",
                        "enum": ["day", "gtc", "ioc", "fok"],
                        "description": "Time in force (default: day)",
                        "default": "day"
                    }
                },
                "required": ["user_id", "account_number", "symbol", "side", "quantity", "order_type"]
            },
        ),
        types.Tool(
            name="confirm_order",
            description="Confirm and submit an order preview",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID who owns the account"
                    },
                    "preview_token": {
                        "type": "string",
                        "description": "Preview token from create_equity_order"
                    },
                    "confirmation": {
                        "type": "string",
                        "description": "Must be 'CONFIRM' to execute the order"
                    }
                },
                "required": ["user_id", "preview_token", "confirmation"]
            },
        ),
        types.Tool(
            name="list_orders",
            description="List orders for an account",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID who owns the account"
                    },
                    "account_number": {
                        "type": "string",
                        "description": "Account number to list orders for"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "submitted", "filled", "cancelled", "rejected"],
                        "description": "Filter by order status"
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
            name="cancel_order",
            description="Cancel an existing order",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID who owns the account"
                    },
                    "order_id": {
                        "type": "string",
                        "description": "Order ID to cancel"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Cancellation reason"
                    }
                },
                "required": ["user_id", "order_id"]
            },
        ),
    ]