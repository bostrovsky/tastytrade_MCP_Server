"""Market data tool definitions."""
from typing import Any

import mcp.types as types


def get_market_data_tools() -> list[types.Tool]:
    """Get market data tool definitions."""
    return [
        types.Tool(
            name="search_symbols",
            description="Search for trading symbols and instruments",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID who is searching"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query for symbols"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 10)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    },
                    "asset_type": {
                        "type": "string",
                        "enum": ["ALL", "EQUITY", "OPTION", "ETF", "FUTURE"],
                        "description": "Filter by asset type (default: ALL)",
                        "default": "ALL"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["text", "json"],
                        "description": "Output format (default: text)",
                        "default": "text"
                    }
                },
                "required": ["user_id", "query"]
            },
        ),
        types.Tool(
            name="search_symbols_advanced",
            description="Advanced search for trading symbols with filtering by price, asset type, and options availability",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID who is searching"
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query for symbols"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 10)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    },
                    "asset_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by asset types (equity, etf, index, etc.)"
                    },
                    "min_price": {
                        "type": "number",
                        "description": "Minimum stock price filter"
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Maximum stock price filter"
                    },
                    "options_enabled": {
                        "type": "boolean",
                        "description": "Filter for symbols with options trading"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["text", "json"],
                        "description": "Output format (default: text)",
                        "default": "text"
                    }
                },
                "required": ["user_id", "query"]
            },
        ),
        types.Tool(
            name="get_quotes",
            description="Get real-time quote data for trading symbols",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID requesting quotes"
                    },
                    "symbols": {
                        "oneOf": [
                            {"type": "string", "description": "Single symbol"},
                            {"type": "array", "items": {"type": "string"}, "description": "List of symbols"}
                        ],
                        "description": "Symbol(s) to get quotes for"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["text", "json"],
                        "description": "Output format (default: text)",
                        "default": "text"
                    }
                },
                "required": ["user_id", "symbols"]
            },
        ),
        types.Tool(
            name="get_historical_data",
            description="Get historical price data for analysis and charting",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User ID requesting data"
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Symbol to get historical data for"
                    },
                    "timeframe": {
                        "type": "string",
                        "enum": ["1min", "5min", "15min", "30min", "1hour", "1day", "1week", "1month"],
                        "description": "Time interval for data points",
                        "default": "1day"
                    },
                    "start_date": {
                        "type": "string",
                        "format": "date",
                        "description": "Start date (YYYY-MM-DD)"
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date",
                        "description": "End date (YYYY-MM-DD)"
                    },
                    "include_extended": {
                        "type": "boolean",
                        "description": "Include extended hours data (default: false)",
                        "default": False
                    },
                    "format": {
                        "type": "string",
                        "enum": ["text", "json"],
                        "description": "Output format (default: text)",
                        "default": "text"
                    }
                },
                "required": ["user_id", "symbol", "start_date", "end_date"]
            },
        ),
    ]


def get_streaming_tools() -> list[types.Tool]:
    """Get WebSocket streaming tool definitions."""
    return [
        types.Tool(
            name="subscribe_market_stream",
            description="Subscribe to real-time market data streams via WebSocket",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of symbols to subscribe to (max 100)",
                        "maxItems": 100
                    },
                    "data_types": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["quote", "trade", "status"]
                        },
                        "description": "Types of data to stream (default: quote, trade)",
                        "default": ["quote", "trade"]
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID for authentication"
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Optional session ID for connection pooling"
                    }
                },
                "required": ["symbols"]
            },
        ),
        types.Tool(
            name="unsubscribe_market_stream",
            description="Unsubscribe from market data streams",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of symbols to unsubscribe (omit to unsubscribe all)"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID for authentication"
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Optional session ID"
                    }
                },
                "required": []
            },
        ),
        types.Tool(
            name="get_stream_status",
            description="Get current WebSocket stream status and subscriptions",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            },
        ),
        types.Tool(
            name="get_stream_data",
            description="Get latest data from WebSocket streams",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Symbols to get data for"
                    },
                    "data_type": {
                        "type": "string",
                        "enum": ["latest", "all"],
                        "description": "Type of data to retrieve (default: latest)",
                        "default": "latest"
                    }
                },
                "required": ["symbols"]
            },
        ),
        types.Tool(
            name="get_stream_metrics",
            description="Get WebSocket streaming performance metrics",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            },
        ),
        types.Tool(
            name="shutdown_streams",
            description="Gracefully shutdown all WebSocket connections",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            },
        ),
    ]