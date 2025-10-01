"""Emergency control tool definitions."""
from typing import Any

import mcp.types as types


def get_emergency_tools() -> list[types.Tool]:
    """Get emergency control tool definitions."""
    return [
        types.Tool(
            name="panic_button",
            description="Execute emergency panic button to immediately cancel all pending orders",
            inputSchema={
                "type": "object",
                "properties": {
                    "account_number": {
                        "type": "string",
                        "description": "Account number to execute panic button for"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for panic button activation",
                        "default": "User initiated panic button"
                    }
                },
                "required": ["account_number"]
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
                "required": ["account_number"]
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
                        "description": "Account number for complete emergency stop"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for complete emergency stop",
                        "default": "Complete emergency stop"
                    }
                },
                "required": ["account_number"]
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
    ]