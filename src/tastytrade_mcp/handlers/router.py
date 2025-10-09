"""Universal handler router - routes ALL handlers based on environment.

This module provides a single routing mechanism for all MCP handlers,
eliminating the need for separate router files per handler category.

Architecture:
    - Single route_to_handler() function
    - Environment detection via TASTYTRADE_USE_PRODUCTION env var
    - Routes to OAuth handlers (production) or SDK handlers (sandbox)
    - Handler registry maps handler names to their implementations
"""

import os
from typing import Any, Callable, Dict
import mcp.types as types
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


# Handler Registry: Maps handler names to their OAuth and SDK implementations
HANDLER_REGISTRY: Dict[str, Dict[str, str]] = {
    # Account handlers
    "get_accounts": {
        "oauth": "tastytrade_mcp.handlers.accounts_oauth:handle_get_accounts",
        "sdk": "tastytrade_mcp.handlers.accounts:handle_get_accounts"
    },
    "get_balances": {
        "oauth": "tastytrade_mcp.handlers.accounts_oauth:handle_get_balances",
        "sdk": "tastytrade_mcp.handlers.accounts:handle_get_balances"
    },

    # Emergency handlers
    "panic_button": {
        "oauth": "tastytrade_mcp.handlers.emergency_oauth:handle_panic_button",
        "sdk": "tastytrade_mcp.handlers.emergency:handle_panic_button"
    },
    "emergency_exit": {
        "oauth": "tastytrade_mcp.handlers.emergency_oauth:handle_emergency_exit",
        "sdk": "tastytrade_mcp.handlers.emergency:handle_emergency_exit"
    },
    "halt_trading": {
        "oauth": "tastytrade_mcp.handlers.emergency_oauth:handle_halt_trading",
        "sdk": "tastytrade_mcp.handlers.emergency:handle_halt_trading"
    },
    "resume_trading": {
        "oauth": "tastytrade_mcp.handlers.emergency_oauth:handle_resume_trading",
        "sdk": "tastytrade_mcp.handlers.emergency:handle_resume_trading"
    },
    "emergency_stop_all": {
        "oauth": "tastytrade_mcp.handlers.emergency_oauth:handle_emergency_stop_all",
        "sdk": "tastytrade_mcp.handlers.emergency:handle_emergency_stop_all"
    },
    "create_circuit_breaker": {
        "oauth": "tastytrade_mcp.handlers.emergency_oauth:handle_create_circuit_breaker",
        "sdk": "tastytrade_mcp.handlers.emergency:handle_create_circuit_breaker"
    },
    "check_emergency_conditions": {
        "oauth": "tastytrade_mcp.handlers.emergency_oauth:handle_check_emergency_conditions",
        "sdk": "tastytrade_mcp.handlers.emergency:handle_check_emergency_conditions"
    },
    "get_emergency_history": {
        "oauth": "tastytrade_mcp.handlers.emergency_oauth:handle_get_emergency_history",
        "sdk": "tastytrade_mcp.handlers.emergency:handle_get_emergency_history"
    },

    # Market data handlers
    "search_symbols": {
        "oauth": "tastytrade_mcp.handlers.market_data_oauth:handle_search_symbols",
        "sdk": "tastytrade_mcp.handlers.market_data:handle_search_symbols"
    },
    "get_quotes": {
        "oauth": "tastytrade_mcp.handlers.market_data_oauth:handle_get_quotes",
        "sdk": "tastytrade_mcp.handlers.market_data:handle_get_quotes"
    },
    "search_symbols_advanced": {
        "oauth": "tastytrade_mcp.handlers.advanced_market_oauth:handle_search_symbols_advanced",
        "sdk": "tastytrade_mcp.handlers.advanced_market:handle_search_symbols_advanced"
    },
    "get_options_chain": {
        "oauth": "tastytrade_mcp.handlers.advanced_market_oauth:handle_get_options_chain",
        "sdk": "tastytrade_mcp.handlers.advanced_market:handle_get_options_chain"
    },

    # Position handlers
    "get_positions": {
        "oauth": "tastytrade_mcp.handlers.positions_oauth:handle_get_positions",
        "sdk": "tastytrade_mcp.handlers.positions:handle_get_positions"
    },
    "monitor_position_alerts": {
        "oauth": "tastytrade_mcp.handlers.advanced_positions_oauth:handle_monitor_position_alerts",
        "sdk": "tastytrade_mcp.handlers.advanced_positions:handle_monitor_position_alerts"
    },

    # Analysis handlers
    "analyze_portfolio": {
        "oauth": "tastytrade_mcp.handlers.analysis_oauth:handle_analyze_portfolio",
        "sdk": "tastytrade_mcp.handlers.analysis:handle_analyze_portfolio"
    },
    "suggest_rebalancing": {
        "oauth": "tastytrade_mcp.handlers.analysis_oauth:handle_suggest_rebalancing",
        "sdk": "tastytrade_mcp.handlers.analysis:handle_suggest_rebalancing"
    },

    # Trading handlers
    "create_order": {
        "oauth": "tastytrade_mcp.handlers.trading_oauth:handle_create_order",
        "sdk": "tastytrade_mcp.handlers.trading:handle_create_order"
    },
    "create_equity_order": {
        "oauth": "tastytrade_mcp.handlers.trading_oauth:handle_create_equity_order",
        "sdk": "tastytrade_mcp.handlers.trading:handle_create_equity_order"
    },
    "create_options_order": {
        "oauth": "tastytrade_mcp.handlers.trading_oauth:handle_create_options_order",
        "sdk": "tastytrade_mcp.handlers.trading:handle_create_options_order"
    },
    "confirm_order": {
        "oauth": "tastytrade_mcp.handlers.trading_oauth:handle_confirm_order",
        "sdk": "tastytrade_mcp.handlers.trading:handle_confirm_order"
    },
    "cancel_order": {
        "oauth": "tastytrade_mcp.handlers.trading_oauth:handle_cancel_order",
        "sdk": "tastytrade_mcp.handlers.trading:handle_cancel_order"
    },
    "list_orders": {
        "oauth": "tastytrade_mcp.handlers.trading_oauth:handle_list_orders",
        "sdk": "tastytrade_mcp.handlers.trading:handle_list_orders"
    },
    "set_stop_loss": {
        "oauth": "tastytrade_mcp.handlers.trading_oauth:handle_set_stop_loss",
        "sdk": "tastytrade_mcp.handlers.trading:handle_set_stop_loss"
    },
    "set_take_profit": {
        "oauth": "tastytrade_mcp.handlers.trading_oauth:handle_set_take_profit",
        "sdk": "tastytrade_mcp.handlers.trading:handle_set_take_profit"
    },
}


def _import_handler(handler_path: str) -> Callable:
    """Dynamically import a handler function.

    Args:
        handler_path: Path in format "module.path:function_name"

    Returns:
        Callable: The imported handler function

    Raises:
        ImportError: If module or function cannot be imported
    """
    try:
        module_path, function_name = handler_path.split(":")
        module = __import__(module_path, fromlist=[function_name])
        handler = getattr(module, function_name)
        return handler
    except Exception as e:
        logger.error(f"Failed to import handler from {handler_path}: {e}")
        raise ImportError(f"Cannot import handler: {handler_path}") from e


async def route_to_handler(handler_name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Route handler call to appropriate implementation based on environment.

    This is the single entry point for ALL handler routing in the system.

    Architecture:
        1. Check TASTYTRADE_USE_PRODUCTION environment variable
        2. Select 'oauth' or 'sdk' implementation from registry
        3. Dynamically import the handler
        4. Execute and return result

    Args:
        handler_name: Name of handler to execute (e.g., "panic_button", "get_accounts")
        arguments: Arguments to pass to handler

    Returns:
        List[types.TextContent]: Handler result

    Raises:
        ValueError: If handler_name not found in registry
        ImportError: If handler implementation cannot be imported

    Example:
        >>> # In sandbox mode (TASTYTRADE_USE_PRODUCTION=false)
        >>> result = await route_to_handler("panic_button", {"account_number": "5WW54184"})
        >>> # Routes to: tastytrade_mcp.handlers.emergency:handle_panic_button

        >>> # In production mode (TASTYTRADE_USE_PRODUCTION=true)
        >>> result = await route_to_handler("panic_button", {"account_number": "5WW54184"})
        >>> # Routes to: tastytrade_mcp.handlers.emergency_oauth:handle_panic_button
    """
    # Check if handler exists in registry
    if handler_name not in HANDLER_REGISTRY:
        error_msg = f"Handler '{handler_name}' not found in registry. Available handlers: {', '.join(HANDLER_REGISTRY.keys())}"
        logger.error(error_msg)
        return [types.TextContent(
            type="text",
            text=f"Error: {error_msg}"
        )]

    # Determine environment: production (OAuth) or sandbox (SDK)
    use_production = os.getenv('TASTYTRADE_USE_PRODUCTION', 'false').lower() == 'true'
    mode = "oauth" if use_production else "sdk"
    env_name = "PRODUCTION" if use_production else "SANDBOX"

    # Get handler path from registry
    handler_config = HANDLER_REGISTRY[handler_name]
    handler_path = handler_config.get(mode)

    if not handler_path:
        error_msg = f"No {mode.upper()} implementation found for handler '{handler_name}'"
        logger.error(error_msg)
        return [types.TextContent(
            type="text",
            text=f"Error: {error_msg}"
        )]

    logger.info(f"📍 Routing '{handler_name}' to {mode.upper()} handler ({env_name}): {handler_path}")

    try:
        # Dynamically import and execute handler
        handler = _import_handler(handler_path)
        result = await handler(arguments)
        return result

    except ImportError as e:
        error_msg = f"Failed to import {mode.upper()} handler for '{handler_name}': {str(e)}"
        logger.error(error_msg, exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error: {error_msg}"
        )]

    except Exception as e:
        error_msg = f"Error executing handler '{handler_name}': {str(e)}"
        logger.error(error_msg, exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error: {error_msg}"
        )]


def register_handler(handler_name: str, oauth_path: str, sdk_path: str) -> None:
    """Register a new handler in the routing registry.

    This allows handlers to be added dynamically without modifying this file.

    Args:
        handler_name: Name of the handler
        oauth_path: Path to OAuth implementation (module:function format)
        sdk_path: Path to SDK implementation (module:function format)

    Example:
        >>> register_handler(
        ...     "my_custom_handler",
        ...     "my_module.oauth:handle_my_custom",
        ...     "my_module.sdk:handle_my_custom"
        ... )
    """
    HANDLER_REGISTRY[handler_name] = {
        "oauth": oauth_path,
        "sdk": sdk_path
    }
    logger.info(f"Registered handler '{handler_name}' with OAuth: {oauth_path}, SDK: {sdk_path}")


def list_registered_handlers() -> list[str]:
    """Get list of all registered handler names.

    Returns:
        List of handler names currently in the registry
    """
    return list(HANDLER_REGISTRY.keys())
