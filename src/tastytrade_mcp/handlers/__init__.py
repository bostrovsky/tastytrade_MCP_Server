"""Handler modules for TastyTrade MCP.

This package contains modular handlers extracted from the main.py file,
organized by functionality for better maintainability and code organization.
"""

# Import health check handler
from .health import handle_health_check

# Import function-based handlers from system.py
from .system import (
    handle_health_check as system_handle_health_check,
    handle_emergency_stop,
    handle_emergency_resume,
    handle_system_status
)

# Import OAuth-based account handlers
from .accounts_oauth import (
    handle_get_accounts,
    handle_get_balances
)

# Import OAuth-based emergency handlers
from .emergency_oauth import (
    handle_panic_button,
    handle_emergency_exit,
    handle_halt_trading,
    handle_resume_trading,
    handle_emergency_stop_all,
    handle_create_circuit_breaker,
    handle_check_emergency_conditions,
    handle_get_emergency_history,
)

# Import OAuth-based market data handlers
from .market_data_oauth import (
    handle_search_symbols,
    handle_get_quotes,
)
# Import OAuth-based advanced market data handlers
from .advanced_market_oauth import (
    handle_search_symbols_advanced,
    handle_get_options_chain,
)

# Import OAuth-based trading handlers
from .trading_oauth import (
    handle_create_equity_order,
    handle_create_options_order,
    handle_confirm_order,
    handle_cancel_order,
    handle_list_orders,
    handle_set_stop_loss,
    handle_set_take_profit,
)

# Import OAuth-based position handlers
from .positions_oauth import (
    handle_get_positions,
)
# Import OAuth-based advanced position handlers
from .advanced_positions_oauth import (
    handle_monitor_position_alerts,
)

# Import OAuth-based analysis handlers
from .analysis_oauth import (
    handle_suggest_rebalancing,
    handle_analyze_portfolio,
)

# Import registry functions
from .registry import (
    register_handler,
    get_handler,
    list_handlers,
    dispatch,
    auto_register_handlers
)

__all__ = [
    # System function handlers
    "handle_health_check",
    "handle_emergency_stop",
    "handle_emergency_resume",
    "handle_system_status",
    # Account function handlers
    "handle_get_accounts",
    "handle_get_balances",
    # Emergency function handlers
    "handle_panic_button",
    "handle_emergency_exit",
    "handle_halt_trading",
    "handle_resume_trading",
    "handle_emergency_stop_all",
    "handle_create_circuit_breaker",
    "handle_check_emergency_conditions",
    "handle_get_emergency_history",
    # Market data function handlers
    "handle_search_symbols",
    "handle_search_symbols_advanced",
    "handle_get_quotes",
    "handle_get_options_chain",
    # Trading function handlers
    "handle_create_equity_order",
    "handle_create_options_order",
    "handle_confirm_order",
    "handle_cancel_order",
    "handle_list_orders",
    "handle_set_stop_loss",
    "handle_set_take_profit",
    # Position function handlers
    "handle_get_positions",
    "handle_analyze_portfolio",
    "handle_monitor_position_alerts",
    # Analysis function handlers
    "handle_suggest_rebalancing",
    # Registry functions
    "register_handler",
    "get_handler",
    "list_handlers",
    "dispatch",
    "auto_register_handlers"
]