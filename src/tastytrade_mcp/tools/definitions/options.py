"""Options trading tool definitions."""
from typing import Any

import mcp.types as types


def get_options_tools() -> list[types.Tool]:
    """Get options trading tool definitions."""
    return [
        types.Tool(
            name="create_options_order",
            description="Create a preview for an options order with strategy recognition and risk assessment",
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
                    "underlying_symbol": {
                        "type": "string",
                        "description": "Underlying symbol (e.g., AAPL)"
                    },
                    "legs": {
                        "type": "array",
                        "description": "Options legs for the strategy",
                        "items": {
                            "type": "object",
                            "properties": {
                                "option_type": {
                                    "type": "string",
                                    "enum": ["call", "put"],
                                    "description": "Option type"
                                },
                                "action": {
                                    "type": "string",
                                    "enum": ["buy_to_open", "buy_to_close", "sell_to_open", "sell_to_close"],
                                    "description": "Order action"
                                },
                                "quantity": {
                                    "type": "integer",
                                    "description": "Number of contracts",
                                    "minimum": 1,
                                    "maximum": 100
                                },
                                "strike_price": {
                                    "type": "number",
                                    "description": "Strike price"
                                },
                                "expiration_date": {
                                    "type": "string",
                                    "description": "Expiration date (YYYY-MM-DD)"
                                },
                                "limit_price": {
                                    "type": "number",
                                    "description": "Limit price per contract (optional)"
                                }
                            },
                            "required": ["option_type", "action", "quantity", "strike_price", "expiration_date"]
                        },
                        "minItems": 1,
                        "maxItems": 4
                    },
                    "time_in_force": {
                        "type": "string",
                        "enum": ["day", "gtc", "ioc", "fok"],
                        "description": "Time in force (default: day)",
                        "default": "day"
                    }
                },
                "required": ["user_id", "account_number", "underlying_symbol", "legs"]
            },
        ),
        types.Tool(
            name="get_options_chain",
            description="Get options chain data for a symbol",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID who owns the account"
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Underlying symbol"
                    },
                    "expiration_date": {
                        "type": "string",
                        "description": "Expiration date (YYYY-MM-DD) or 'all' for all dates"
                    },
                    "strike_range": {
                        "type": "integer",
                        "description": "Number of strikes above/below current price (default: 10)",
                        "default": 10
                    },
                    "include_greeks": {
                        "type": "boolean",
                        "description": "Include Greeks in response (default: true)",
                        "default": True
                    },
                    "format": {
                        "type": "string",
                        "enum": ["text", "json"],
                        "description": "Output format (default: text)",
                        "default": "text"
                    }
                },
                "required": ["user_id", "symbol"]
            },
        ),
        types.Tool(
            name="analyze_options_strategy",
            description="Analyze an options strategy for risk/reward metrics",
            inputSchema={
                "type": "object",
                "properties": {
                    "underlying_symbol": {
                        "type": "string",
                        "description": "Underlying symbol"
                    },
                    "underlying_price": {
                        "type": "number",
                        "description": "Current underlying price"
                    },
                    "legs": {
                        "type": "array",
                        "description": "Options legs to analyze",
                        "items": {
                            "type": "object",
                            "properties": {
                                "option_type": {
                                    "type": "string",
                                    "enum": ["call", "put"]
                                },
                                "side": {
                                    "type": "string",
                                    "enum": ["buy", "sell"]
                                },
                                "quantity": {
                                    "type": "integer"
                                },
                                "strike_price": {
                                    "type": "number"
                                },
                                "expiration_date": {
                                    "type": "string"
                                },
                                "premium": {
                                    "type": "number",
                                    "description": "Premium per contract"
                                }
                            },
                            "required": ["option_type", "side", "quantity", "strike_price", "expiration_date", "premium"]
                        }
                    },
                    "format": {
                        "type": "string",
                        "enum": ["text", "json"],
                        "description": "Output format (default: text)",
                        "default": "text"
                    }
                },
                "required": ["underlying_symbol", "underlying_price", "legs"]
            },
        ),
    ]