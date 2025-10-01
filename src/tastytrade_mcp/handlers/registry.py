"""Handler registry for dynamic dispatch of MCP tool calls."""
from typing import Any, Callable, Dict, Optional
import mcp.types as types

# Registry to store all handler functions
_handler_registry: Dict[str, Callable] = {}


def register_handler(name: str):
    """Decorator to register a handler function.

    Usage:
        @register_handler("get_accounts")
        async def handle_get_accounts(arguments: dict) -> list[types.TextContent]:
            ...
    """
    def decorator(func: Callable):
        _handler_registry[name] = func
        return func
    return decorator


def get_handler(name: str) -> Optional[Callable]:
    """Get a handler function by name."""
    return _handler_registry.get(name)


def list_handlers() -> list[str]:
    """List all registered handler names."""
    return list(_handler_registry.keys())


async def dispatch(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Dispatch a tool call to the appropriate handler.

    Args:
        name: The tool name
        arguments: The tool arguments

    Returns:
        The handler response
    """
    handler = get_handler(name)

    if not handler:
        return [types.TextContent(
            type="text",
            text=f"Error: No handler registered for tool '{name}'"
        )]

    try:
        return await handler(arguments)
    except Exception as e:
        return [types.TextContent(
            type="text",
            text=f"Error executing '{name}': {str(e)}"
        )]


def auto_register_handlers():
    """Auto-register all handlers from handler modules."""
    # Import all handler modules to trigger decorator registration
    from . import system, accounts, emergency
    # As we add more modules, import them here:
    # from . import market_data, trading, streaming, analysis

    # Return count for debugging
    return len(_handler_registry)