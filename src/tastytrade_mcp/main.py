"""TastyTrade MCP Server entry point."""
import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    # Try current directory
    load_dotenv()
from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.handlers import (
    handle_health_check,
    handle_get_accounts,
    handle_get_balances,
    handle_panic_button,
    handle_emergency_exit,
    handle_halt_trading,
    handle_resume_trading,
    handle_emergency_stop_all,
    handle_create_circuit_breaker,
    handle_check_emergency_conditions,
    handle_get_emergency_history,
    handle_search_symbols,
    handle_search_symbols_advanced,
    handle_get_quotes,
    # handle_get_historical_data,  # REMOVED: Fake tool - API doesn't exist
    handle_get_options_chain,
    handle_scan_opportunities,
    handle_create_equity_order,
    handle_create_options_order,
    handle_confirm_order,
    handle_cancel_order,
    handle_list_orders,
    handle_set_stop_loss,
    handle_set_take_profit,
    handle_get_positions,
    # handle_get_positions_with_greeks,  # REMOVED: Fake tool - Greeks don't exist in API
    handle_analyze_portfolio,
    handle_monitor_position_alerts,
    handle_analyze_position_correlation,
    handle_bulk_position_update,
    handle_analyze_options_strategy,
    handle_suggest_rebalancing,
)
from tastytrade_mcp.handlers.option_chain_oauth import (
    handle_get_option_chain,
    handle_find_options_by_delta,
)
from tastytrade_mcp.handlers.realtime_quotes_oauth import (
    handle_get_realtime_quotes,
    handle_stream_option_quotes,
)
from tastytrade_mcp.handlers.simple_option_quotes import (
    handle_get_option_quotes,
)
from tastytrade_mcp.handlers.help import handle_help
from tastytrade_mcp.handlers.shortcuts import (
    handle_list_shortcuts,
    handle_create_shortcut,
    handle_execute_shortcut,
    handle_test_shortcut,
    handle_delete_shortcut,
)
from tastytrade_mcp.handlers.streaming_oauth import (
    handle_subscribe_market_stream,
    handle_unsubscribe_market_stream,
    handle_get_stream_data,
    handle_get_stream_status,
    handle_get_stream_metrics,
    handle_shutdown_streams,
)
from tastytrade_mcp.services.websocket import WebSocketManager

# Configure logging to stderr only (stdout must be clean for MCP JSON-RPC)
import sys
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Detect and log mode
settings = get_settings()
mode = "DATABASE" if settings.use_database_mode else "SIMPLE"
logger.info(f"🚀 Starting TastyTrade MCP Server in {mode} mode")

# Create server instance
server = Server("tastytrade-mcp")

# Initialize WebSocket manager
websocket_manager = WebSocketManager()


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    tools = [
        types.Tool(
            name="health_check",
            description="Check if the MCP server is running",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            },
        ),
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
                "required": []
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
                "required": ["account_number"]
            },
        ),
        # REMOVED: TastyTrade API doesn't provide Greeks data
        # Greeks would need to be calculated client-side using Black-Scholes
        # types.Tool(
        #     name="get_positions_with_greeks",
        #     description="Get all positions with Greek data for options analysis",
        #     inputSchema={
        #         "type": "object",
        #         "properties": {
        #             "user_id": {
        #                 "type": "string",
        #                 "description": "User ID who owns the account"
        #             },
        #             "account_number": {
        #                 "type": "string",
        #                 "description": "Account number to get positions for"
        #             },
        #             "format": {
        #                 "type": "string",
        #                 "enum": ["text", "json"],
        #                 "description": "Output format (default: text)",
        #                 "default": "text"
        #             }
        #         },
        #         "required": ["account_number"]
        #     },
        # ),
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
                "required": ["account_number"]
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
                "required": ["account_number"]
            },
        ),
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
                "required": ["query"]
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
                "required": ["query"]
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
                "required": ["symbols"]
            },
        ),
        types.Tool(
            name="get_realtime_quotes",
            description="Get real-time quotes using WebSocket streaming for accurate live prices",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "string",
                        "description": "Comma-separated list of symbols to get quotes for"
                    },
                    "duration": {
                        "type": "integer",
                        "description": "How long to stream quotes in seconds (default: 10)",
                        "default": 10
                    },
                    "format": {
                        "type": "string",
                        "enum": ["text", "json"],
                        "description": "Output format (default: text)",
                        "default": "text"
                    }
                },
                "required": ["symbols"]
            },
        ),
        # REMOVED: TastyTrade API doesn't provide historical data endpoint
        # Would require integration with separate market data provider
        # types.Tool(
        #     name="get_historical_data",
        #     description="Get historical price data for analysis and charting",
        #     inputSchema={
        #         "type": "object",
        #         "properties": {
        #             "user_id": {
        #                 "type": "string",
        #                 "description": "User ID requesting data"
        #             },
        #             "symbol": {
        #                 "type": "string",
        #                 "description": "Symbol to get historical data for"
        #             },
        #             "timeframe": {
        #                 "type": "string",
        #                 "enum": ["1min", "5min", "15min", "30min", "1hour", "1day", "1week", "1month"],
        #                 "description": "Time interval for data points",
        #                 "default": "1day"
        #             },
        #             "start_date": {
        #                 "type": "string",
        #                 "format": "date",
        #                 "description": "Start date (YYYY-MM-DD)"
        #             },
        #             "end_date": {
        #                 "type": "string",
        #                 "format": "date",
        #                 "description": "End date (YYYY-MM-DD)"
        #             },
        #             "include_extended": {
        #                 "type": "boolean",
        #                 "description": "Include extended hours data (default: false)",
        #                 "default": False
        #             },
        #             "format": {
        #                 "type": "string",
        #                 "enum": ["text", "json"],
        #                 "description": "Output format (default: text)",
        #                 "default": "text"
        #             }
        #         },
        #         "required": ["symbol", "start_date", "end_date"]
        #     },
        # ),
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
        types.Tool(
            name="help",
            description="Get help and documentation for available MCP tools",
            inputSchema={
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Optional: Name of specific tool to get detailed help for"
                    }
                },
                "required": []
            },
        ),
        types.Tool(
            name="list_shortcuts",
            description="List all available user-defined shortcuts",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            },
        ),
        types.Tool(
            name="create_shortcut",
            description="Create a new shortcut that combines multiple tool calls",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Unique name for the shortcut"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of what this shortcut does"
                    },
                    "tools": {
                        "type": "array",
                        "description": "List of tools to execute in sequence",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "args": {"type": "object"}
                            }
                        }
                    }
                },
                "required": ["name", "tools"]
            },
        ),
        types.Tool(
            name="execute_shortcut",
            description="Execute a saved shortcut by name",
            inputSchema={
                "type": "object",
                "properties": {
                    "shortcut_name": {
                        "type": "string",
                        "description": "Name of the shortcut to execute"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID (required for authentication)"
                    },
                    "account_number": {
                        "type": "string",
                        "description": "Account number (optional, used by tools that need it)"
                    }
                },
                "required": ["shortcut_name"]
            },
        ),
        types.Tool(
            name="test_shortcut",
            description="Test a shortcut by showing what it would do without executing",
            inputSchema={
                "type": "object",
                "properties": {
                    "shortcut_name": {
                        "type": "string",
                        "description": "Name of the shortcut to test"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID (required for authentication)"
                    },
                    "account_number": {
                        "type": "string",
                        "description": "Account number (optional)"
                    }
                },
                "required": ["shortcut_name"]
            },
        ),
        types.Tool(
            name="delete_shortcut",
            description="Delete an existing shortcut",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the shortcut to delete"
                    }
                },
                "required": ["name"]
            },
        ),
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
                "required": ["account_number", "symbol", "side", "quantity", "order_type"]
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
                "required": ["preview_token", "confirmation"]
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
                "required": []
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
                "required": ["order_id"]
            },
        ),
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
                "required": ["account_number", "underlying_symbol", "legs"]
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
                "required": ["symbol"]
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
        types.Tool(
            name="monitor_position_alerts",
            description="Monitor position alerts for P&L thresholds and price movements",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Account number to monitor positions for"
                    },
                    "alert_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Types of alerts to check: pnl_threshold, stop_loss_triggered, take_profit_triggered",
                        "default": ["pnl_threshold", "stop_loss_triggered", "take_profit_triggered"]
                    }
                },
                "required": ["account_number"]
            },
        ),
        types.Tool(
            name="set_stop_loss",
            description="Set stop-loss order for a position",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Account number"
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Position symbol"
                    },
                    "stop_price": {
                        "type": "number",
                        "description": "Stop-loss trigger price"
                    },
                    "order_type": {
                        "type": "string",
                        "enum": ["market", "limit"],
                        "description": "Order type when stop is triggered",
                        "default": "market"
                    },
                    "limit_price": {
                        "type": "number",
                        "description": "Limit price for stop-limit orders (optional)"
                    }
                },
                "required": ["account_number", "symbol", "stop_price"]
            },
        ),
        types.Tool(
            name="set_take_profit",
            description="Set take-profit order for a position",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Account number"
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Position symbol"
                    },
                    "target_price": {
                        "type": "number",
                        "description": "Take-profit target price"
                    },
                    "order_type": {
                        "type": "string",
                        "enum": ["market", "limit"],
                        "description": "Order type when target is reached",
                        "default": "limit"
                    }
                },
                "required": ["account_number", "symbol", "target_price"]
            },
        ),
        types.Tool(
            name="analyze_position_correlation",
            description="Analyze correlation between positions to identify concentration risks",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Account number"
                    },
                    "lookback_days": {
                        "type": "integer",
                        "description": "Days of historical data for correlation analysis",
                        "default": 30
                    },
                    "correlation_threshold": {
                        "type": "number",
                        "description": "Correlation threshold for risk identification",
                        "default": 0.7
                    }
                },
                "required": ["account_number"]
            },
        ),
        types.Tool(
            name="suggest_rebalancing",
            description="Generate portfolio rebalancing suggestions based on target allocations",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Account number"
                    },
                    "target_allocations": {
                        "type": "object",
                        "description": "Target allocation percentages by symbol or category",
                        "additionalProperties": {"type": "number"}
                    },
                    "rebalance_threshold": {
                        "type": "number",
                        "description": "Minimum deviation percentage to trigger rebalancing",
                        "default": 5.0
                    }
                },
                "required": ["account_number", "target_allocations"]
            },
        ),
        types.Tool(
            name="bulk_position_update",
            description="Perform bulk operations on multiple positions",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Account number"
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["set_stop_loss", "set_take_profit", "close_positions"],
                        "description": "Bulk operation to perform"
                    },
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of symbols to apply operation to"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "Operation-specific parameters",
                        "additionalProperties": True
                    }
                },
                "required": ["account_number", "operation", "symbols"]
            },
        ),

        # Emergency Control Tools
        types.Tool(
            name="panic_button",
            description="Execute emergency panic button to immediately cancel all pending orders",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Account number to execute panic button for (optional - halts all accounts if not provided)"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for panic button activation",
                        "default": "User initiated panic button"
                    }
                },
                "required": []
            },
        ),
        types.Tool(
            name="emergency_exit",
            description="Emergency exit all positions at market prices",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Account number to exit all positions for"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for emergency exit",
                        "default": "Emergency position exit"
                    }
                },
                "required": ["account_number"]
            },
        ),
        types.Tool(
            name="halt_trading",
            description="Halt all trading activity for an account",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Account number to halt trading for"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for trading halt"
                    },
                    "override_required": {
                        "type": "boolean",
                        "description": "Whether manual override is required to resume",
                        "default": True
                    }
                },
                "required": ["account_number", "reason"]
            },
        ),
        types.Tool(
            name="resume_trading",
            description="Resume trading after halt with safety checks",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Account number to resume trading for"
                    },
                    "halt_id": {
                        "type": "string",
                        "description": "ID of the trading halt to resume"
                    },
                    "justification": {
                        "type": "string",
                        "description": "Justification for resuming trading"
                    }
                },
                "required": ["account_number", "halt_id", "justification"]
            },
        ),
        types.Tool(
            name="check_emergency_conditions",
            description="Check comprehensive emergency conditions for an account",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Account number to check emergency conditions for"
                    }
                },
                "required": []
            },
        ),
        types.Tool(
            name="create_circuit_breaker",
            description="Create a new circuit breaker for risk management",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Account number to create circuit breaker for"
                    },
                    "breaker_type": {
                        "type": "string",
                        "description": "Type of circuit breaker",
                        "enum": ["daily_loss_limit", "position_size_limit", "concentration_limit", "volatility_threshold"]
                    },
                    "threshold_percentage": {
                        "type": "number",
                        "description": "Threshold percentage for triggering (e.g., 10 for 10%)"
                    },
                    "auto_trigger": {
                        "type": "boolean",
                        "description": "Whether to automatically trigger actions",
                        "default": True
                    }
                },
                "required": ["account_number", "breaker_type", "threshold_percentage"]
            },
        ),
        types.Tool(
            name="emergency_stop_all",
            description="Complete emergency stop: cancel orders, exit positions, and halt trading",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Account number for complete emergency stop (optional - stops all accounts if not provided)"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for complete emergency stop",
                        "default": "Complete emergency stop"
                    }
                },
                "required": []
            },
        ),
        types.Tool(
            name="get_emergency_history",
            description="Get emergency action history for an account",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Account number to get emergency history for"
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Number of hours to look back",
                        "default": 24
                    }
                },
                "required": ["account_number"]
            },
        ),
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
                "required": []
            },
        ),
    ]

    # Log tool count
    tool_count = len(tools)
    logger.info(f"✅ Registered {tool_count} MCP tools")

    return tools


async def format_accounts_response(accounts: list[dict], format_type: str = "text") -> str:
    """Format accounts response based on requested format."""
    if format_type == "json":
        return json.dumps(accounts, indent=2)

    # Text format
    if not accounts:
        return "No accounts found."

    lines = ["TastyTrade Accounts:\n"]
    for acc in accounts:
        lines.append(f"Account: {acc.get('account-number', 'N/A')}")
        lines.append(f"  Nickname: {acc.get('nickname', 'N/A')}")
        lines.append(f"  Type: {acc.get('account-type-name', 'N/A')}")
        lines.append(f"  Status: {'ACTIVE' if not acc.get('is-closed') else 'CLOSED'}")
        lines.append(f"  Margin/Cash: {acc.get('margin-or-cash', 'N/A')}")
        lines.append("")

    return "\n".join(lines)


async def format_balances_response(balances: dict, format_type: str = "text") -> str:
    """Format balances response based on requested format."""
    if format_type == "json":
        return json.dumps(balances, indent=2)

    # Text format
    if not balances:
        return "Balance information not available."

    lines = ["Account Balances:\n"]

    # Key balance metrics
    nlv = balances.get('net-liquidating-value', 0)
    cash = balances.get('cash-balance', 0)
    buying_power = balances.get('buying-power', 0)
    day_trading_bp = balances.get('day-trading-buying-power', 0)
    market_value = balances.get('total-market-value', 0)
    maintenance_req = balances.get('maintenance-requirement', 0)
    maintenance_excess = balances.get('maintenance-excess', 0)

    lines.append(f"Net Liquidating Value: ${nlv:,.2f}")
    lines.append(f"Cash Balance: ${cash:,.2f}")
    lines.append(f"Total Market Value: ${market_value:,.2f}")
    lines.append("")
    lines.append("Buying Power:")
    lines.append(f"  Standard: ${buying_power:,.2f}")
    lines.append(f"  Day Trading: ${day_trading_bp:,.2f}")
    lines.append("")
    lines.append("Margin Requirements:")
    lines.append(f"  Maintenance Requirement: ${maintenance_req:,.2f}")
    lines.append(f"  Maintenance Excess: ${maintenance_excess:,.2f}")

    return "\n".join(lines)




@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    """Handle tool calls."""

    # Health check tool
    if name == "health_check":
        return await handle_health_check(arguments)

    # Account tools
    elif name == "get_accounts":
        return await handle_get_accounts(arguments)
    elif name == "get_balances":
        return await handle_get_balances(arguments)

    # Position tools
    elif name == "get_positions":
        return await handle_get_positions(arguments)
    # REMOVED: get_positions_with_greeks - Fake tool, Greeks don't exist in TastyTrade API
    # elif name == "get_positions_with_greeks":
    #     return await handle_get_positions_with_greeks(arguments)
    elif name == "analyze_portfolio":
        return await handle_analyze_portfolio(arguments)

    # Market data tools
    elif name == "search_symbols":
        return await handle_search_symbols(arguments)
    elif name == "search_symbols_advanced":
        return await handle_search_symbols_advanced(arguments)
    elif name == "get_quotes":
        return await handle_get_quotes(arguments)
    # REMOVED: get_historical_data - Fake tool, endpoint doesn't exist in TastyTrade API
    # elif name == "get_historical_data":
    #     return await handle_get_historical_data(arguments)
    elif name == "get_options_chain":
        return await handle_get_options_chain(arguments)
    elif name == "get_option_chain":  # New handler with better filtering
        return await handle_get_option_chain(arguments)
    elif name == "find_options_by_delta":
        return await handle_find_options_by_delta(arguments)
    elif name == "get_realtime_quotes":
        return await handle_get_realtime_quotes(arguments)
    elif name == "stream_option_quotes":
        return await handle_stream_option_quotes(arguments)
    elif name == "scan_opportunities":
        return await handle_scan_opportunities(arguments)

    # Streaming tools
    elif name == "subscribe_market_stream":
        return await handle_subscribe_market_stream(arguments, websocket_manager)
    elif name == "unsubscribe_market_stream":
        return await handle_unsubscribe_market_stream(arguments, websocket_manager)
    elif name == "get_stream_data":
        return await handle_get_stream_data(arguments, websocket_manager)
    elif name == "get_stream_status":
        return await handle_get_stream_status(arguments, websocket_manager)
    elif name == "get_stream_metrics":
        return await handle_get_stream_metrics(arguments, websocket_manager)
    elif name == "shutdown_streams":
        return await handle_shutdown_streams(arguments, websocket_manager)

    # Help and shortcuts tools
    elif name == "help":
        return await handle_help(arguments)
    elif name == "list_shortcuts":
        return await handle_list_shortcuts(arguments)
    elif name == "create_shortcut":
        return await handle_create_shortcut(arguments)
    elif name == "execute_shortcut":
        return await handle_execute_shortcut(arguments)
    elif name == "test_shortcut":
        return await handle_test_shortcut(arguments)
    elif name == "delete_shortcut":
        return await handle_delete_shortcut(arguments)

    # Trading tools
    elif name == "create_equity_order":
        return await handle_create_equity_order(arguments)
    elif name == "create_options_order":
        return await handle_create_options_order(arguments)
    elif name == "confirm_order":
        return await handle_confirm_order(arguments)
    elif name == "cancel_order":
        return await handle_cancel_order(arguments)
    elif name == "list_orders":
        return await handle_list_orders(arguments)
    elif name == "set_stop_loss":
        return await handle_set_stop_loss(arguments)
    elif name == "set_take_profit":
        return await handle_set_take_profit(arguments)

    # Position management tools
    elif name == "monitor_position_alerts":
        return await handle_monitor_position_alerts(arguments)
    elif name == "analyze_position_correlation":
        return await handle_analyze_position_correlation(arguments)
    elif name == "bulk_position_update":
        return await handle_bulk_position_update(arguments)

    # Analysis tools
    elif name == "analyze_options_strategy":
        return await handle_analyze_options_strategy(arguments)
    elif name == "suggest_rebalancing":
        return await handle_suggest_rebalancing(arguments)

    # Emergency control tools
    elif name == "panic_button":
        return await handle_panic_button(arguments)
    elif name == "emergency_exit":
        return await handle_emergency_exit(arguments)
    elif name == "halt_trading":
        return await handle_halt_trading(arguments)
    elif name == "resume_trading":
        return await handle_resume_trading(arguments)
    elif name == "check_emergency_conditions":
        return await handle_check_emergency_conditions(arguments)
    elif name == "create_circuit_breaker":
        return await handle_create_circuit_breaker(arguments)
    elif name == "emergency_stop_all":
        return await handle_emergency_stop_all(arguments)
    elif name == "get_emergency_history":
        return await handle_get_emergency_history(arguments)

    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the MCP server."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())