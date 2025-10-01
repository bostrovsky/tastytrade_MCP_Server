"""Request dispatcher for routing MCP tool calls to handlers."""
from typing import Any, Dict, List, Optional

import mcp.types as types

from tastytrade_mcp.core.handler_factory import HandlerFactory, get_handler_factory
from tastytrade_mcp.core.service_registry import ServiceRegistry, get_service_registry
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class DispatchError(Exception):
    """Exception raised when dispatch fails."""
    pass


class Dispatcher:
    """Routes MCP tool calls to appropriate handlers.

    The dispatcher is responsible for:
    - Mapping tool names to handlers
    - Managing handler lifecycle
    - Coordinating service dependencies
    - Error handling and logging
    """

    def __init__(
        self,
        factory: Optional[HandlerFactory] = None,
        registry: Optional[ServiceRegistry] = None
    ):
        """Initialize the dispatcher.

        Args:
            factory: Handler factory (uses global if not provided)
            registry: Service registry (uses global if not provided)
        """
        self.factory = factory or get_handler_factory()
        self.registry = registry or get_service_registry()
        self.logger = logger

        # Track dispatch metrics
        self._call_count = {}
        self._error_count = {}

    async def dispatch(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> List[types.TextContent]:
        """Dispatch a tool call to the appropriate handler.

        Args:
            tool_name: Name of the MCP tool
            arguments: Tool arguments

        Returns:
            Handler response as list of TextContent

        Raises:
            DispatchError: If dispatch fails
        """
        self.logger.debug(f"Dispatching tool '{tool_name}' with arguments: {arguments}")

        # Track call metrics
        self._call_count[tool_name] = self._call_count.get(tool_name, 0) + 1

        try:
            # Check if handler exists
            if not self.factory.has_handler(tool_name):
                self.logger.warning(f"No handler registered for tool '{tool_name}'")
                return self._error_response(
                    f"Tool '{tool_name}' is not implemented",
                    "TOOL_NOT_FOUND"
                )

            # Create/retrieve handler
            handler = self.factory.create_handler(tool_name)

            # Execute handler
            result = await handler.handle(arguments)

            self.logger.debug(f"Successfully handled tool '{tool_name}'")
            return result

        except Exception as e:
            self.logger.error(f"Error dispatching tool '{tool_name}': {e}", exc_info=True)
            self._error_count[tool_name] = self._error_count.get(tool_name, 0) + 1

            # Return error response
            return self._error_response(
                f"Failed to execute tool '{tool_name}': {str(e)}",
                "DISPATCH_ERROR"
            )

    def register_handler_module(self, module_name: str) -> None:
        """Register all handlers from a module.

        Args:
            module_name: Module name to import and register
        """
        try:
            import importlib
            module = importlib.import_module(module_name)
            self.factory.register_handlers_from_module(module)
            self.logger.info(f"Registered handlers from module: {module_name}")
        except Exception as e:
            self.logger.error(f"Failed to register module {module_name}: {e}")
            raise DispatchError(f"Failed to register module: {e}")

    def register_handler(
        self,
        tool_name: str,
        handler_class: type,
        singleton: bool = True
    ) -> None:
        """Register a single handler.

        Args:
            tool_name: Tool name
            handler_class: Handler class
            singleton: Whether to use singleton pattern
        """
        self.factory.register_handler(tool_name, handler_class, singleton)
        self.logger.debug(f"Registered handler for tool '{tool_name}'")

    def get_metrics(self) -> Dict[str, Any]:
        """Get dispatch metrics.

        Returns:
            Dictionary with call and error counts
        """
        return {
            "call_count": dict(self._call_count),
            "error_count": dict(self._error_count),
            "total_calls": sum(self._call_count.values()),
            "total_errors": sum(self._error_count.values()),
            "error_rate": (
                sum(self._error_count.values()) / sum(self._call_count.values())
                if self._call_count else 0
            )
        }

    def list_available_tools(self) -> List[str]:
        """List all available tools.

        Returns:
            List of tool names
        """
        return list(self.factory.list_handlers().keys())

    def _error_response(self, message: str, code: str) -> List[types.TextContent]:
        """Create error response.

        Args:
            message: Error message
            code: Error code

        Returns:
            Error response as list of TextContent
        """
        return [
            types.TextContent(
                type="text",
                text=f"❌ Error ({code}): {message}"
            )
        ]

    async def initialize(self) -> None:
        """Initialize the dispatcher and all services."""
        self.logger.info("Initializing dispatcher")

        # Initialize all registered services
        await self.registry.initialize_services()

        # Register handler modules
        self._register_default_handlers()

        self.logger.info(f"Dispatcher initialized with {len(self.list_available_tools())} tools")

    def _register_default_handlers(self) -> None:
        """Register default handler modules."""
        # Import and register handler modules
        modules = [
            "tastytrade_mcp.handlers.system",
            # Add more modules as they're created:
            # "tastytrade_mcp.handlers.accounts",
            # "tastytrade_mcp.handlers.positions",
            # "tastytrade_mcp.handlers.trading",
            # "tastytrade_mcp.handlers.market_data",
            # "tastytrade_mcp.handlers.options",
            # "tastytrade_mcp.handlers.risk",
        ]

        for module_name in modules:
            try:
                self.register_handler_module(module_name)
            except Exception as e:
                self.logger.warning(f"Failed to register module {module_name}: {e}")

    async def cleanup(self) -> None:
        """Clean up dispatcher and all services."""
        self.logger.info("Cleaning up dispatcher")

        # Clean up all services
        await self.registry.cleanup_services()

        # Clear handler instances
        self.factory.clear_instances()

        self.logger.info("Dispatcher cleanup complete")


# Global dispatcher instance
_global_dispatcher: Optional[Dispatcher] = None


def get_dispatcher() -> Dispatcher:
    """Get the global dispatcher instance.

    Returns:
        Global Dispatcher instance
    """
    global _global_dispatcher
    if _global_dispatcher is None:
        _global_dispatcher = Dispatcher()
    return _global_dispatcher