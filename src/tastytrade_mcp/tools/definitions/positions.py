"""Position management tool definitions."""
from typing import Any

import mcp.types as types


def get_position_management_tools() -> list[types.Tool]:
    """Get position management tool definitions."""
    return [
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
    ]