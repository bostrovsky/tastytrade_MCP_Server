"""Scanning and strategy discovery tool definitions."""
from typing import Any

import mcp.types as types


def get_scanning_tools() -> list[types.Tool]:
    """Get scanning and strategy discovery tool definitions."""
    return [
        types.Tool(
            name="scan_opportunities",
            description="Scan for trading opportunities based on strategy criteria",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID who is scanning"
                    },
                    "strategy_type": {
                        "type": "string",
                        "enum": ["covered_call", "cash_secured_put", "strangles"],
                        "description": "Type of strategy to scan for",
                        "default": "covered_call"
                    },
                    "min_return": {
                        "type": "number",
                        "description": "Minimum return percentage required"
                    },
                    "max_risk": {
                        "type": "number",
                        "description": "Maximum risk amount per trade"
                    },
                    "max_dte": {
                        "type": "integer",
                        "description": "Maximum days to expiration",
                        "default": 45
                    },
                    "min_volume": {
                        "type": "integer",
                        "description": "Minimum option volume",
                        "default": 100
                    },
                    "watchlist_symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of symbols to scan (if omitted, uses default watchlist)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return",
                        "default": 20
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
    ]