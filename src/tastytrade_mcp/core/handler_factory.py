"""Handler factory for creating handlers with injected dependencies."""
from typing import Any, Dict, List, Optional, Type
import inspect

from tastytrade_mcp.core.base_handler import BaseHandler
from tastytrade_mcp.core.service_registry import ServiceRegistry, get_service_registry
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class HandlerRegistrationError(Exception):
    """Exception raised when handler registration fails."""
    pass


class HandlerFactory:
    """Factory for creating handlers with dependency injection.

    This factory manages handler registration and creation,
    automatically injecting required dependencies from the service registry.
    """

    def __init__(self, registry: Optional[ServiceRegistry] = None):
        """Initialize the handler factory.

        Args:
            registry: Service registry for dependency injection (uses global if not provided)
        """
        self.registry = registry or get_service_registry()
        self._handler_classes: Dict[str, Type[BaseHandler]] = {}
        self._handler_instances: Dict[str, BaseHandler] = {}
        self._singleton_handlers: set = set()
        self.logger = logger

    def register_handler(
        self,
        tool_name: str,
        handler_class: Type[BaseHandler],
        singleton: bool = True
    ) -> None:
        """Register a handler class for a tool.

        Args:
            tool_name: Name of the MCP tool
            handler_class: Handler class to register
            singleton: If True, reuse the same instance for all requests

        Raises:
            HandlerRegistrationError: If registration fails
        """
        if not issubclass(handler_class, BaseHandler):
            raise HandlerRegistrationError(
                f"{handler_class.__name__} must inherit from BaseHandler"
            )

        self._handler_classes[tool_name] = handler_class
        if singleton:
            self._singleton_handlers.add(tool_name)

        self.logger.debug(f"Registered handler {handler_class.__name__} for tool '{tool_name}'")

    def create_handler(self, tool_name: str) -> BaseHandler:
        """Create or retrieve a handler instance for a tool.

        Args:
            tool_name: Name of the MCP tool

        Returns:
            Handler instance with injected dependencies

        Raises:
            HandlerRegistrationError: If no handler registered for tool
        """
        if tool_name not in self._handler_classes:
            available = ", ".join(self._handler_classes.keys())
            raise HandlerRegistrationError(
                f"No handler registered for tool '{tool_name}'. Available: {available}"
            )

        # Return existing singleton instance if available
        if tool_name in self._singleton_handlers and tool_name in self._handler_instances:
            return self._handler_instances[tool_name]

        handler_class = self._handler_classes[tool_name]
        handler = self._create_handler_instance(handler_class)

        # Store singleton instance
        if tool_name in self._singleton_handlers:
            self._handler_instances[tool_name] = handler

        return handler

    def _create_handler_instance(self, handler_class: Type[BaseHandler]) -> BaseHandler:
        """Create a handler instance with dependency injection.

        Args:
            handler_class: Handler class to instantiate

        Returns:
            Handler instance with injected dependencies
        """
        # Get constructor signature
        sig = inspect.signature(handler_class.__init__)
        kwargs = {}

        # Map parameter names to service names
        param_service_map = {
            'service': 'tastytrade_service',
            'tastytrade_service': 'tastytrade_service',
            'session': 'db_session',
            'db_session': 'db_session',
            'logger': None,  # Special handling for logger
            'websocket_manager': 'websocket_manager',
            'position_manager': 'position_manager',
            'emergency_manager': 'emergency_manager',
        }

        # Inject dependencies based on constructor parameters
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue

            # Handle logger specially
            if param_name == 'logger':
                kwargs['logger'] = get_logger(handler_class.__name__)
                continue

            # Check if we know how to inject this parameter
            service_name = param_service_map.get(param_name)
            if service_name:
                service = self.registry.get(service_name, required=False)
                if service:
                    kwargs[param_name] = service
                elif param.default == inspect.Parameter.empty:
                    # Required parameter but service not available
                    self.logger.warning(
                        f"Service '{service_name}' not available for {handler_class.__name__}.{param_name}"
                    )

        return handler_class(**kwargs)

    def list_handlers(self) -> Dict[str, str]:
        """List all registered handlers.

        Returns:
            Dictionary mapping tool names to handler class names
        """
        return {
            tool: handler_class.__name__
            for tool, handler_class in self._handler_classes.items()
        }

    def has_handler(self, tool_name: str) -> bool:
        """Check if a handler is registered for a tool.

        Args:
            tool_name: Name of the MCP tool

        Returns:
            True if handler is registered
        """
        return tool_name in self._handler_classes

    def clear_instances(self) -> None:
        """Clear all cached handler instances.

        This is useful for testing or when services change.
        """
        self._handler_instances.clear()
        self.logger.debug("Cleared all handler instances")

    def register_handlers_from_module(self, module: Any, prefix: str = "") -> None:
        """Auto-register all handler classes from a module.

        Args:
            module: Module containing handler classes
            prefix: Optional prefix for tool names
        """
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and
                issubclass(obj, BaseHandler) and
                obj != BaseHandler):

                # Generate tool name from class name
                # E.g., GetAccountsHandler -> get_accounts
                tool_name = self._class_name_to_tool_name(name)
                if prefix:
                    tool_name = f"{prefix}_{tool_name}"

                self.register_handler(tool_name, obj)

    @staticmethod
    def _class_name_to_tool_name(class_name: str) -> str:
        """Convert handler class name to tool name.

        Args:
            class_name: Handler class name (e.g., GetAccountsHandler)

        Returns:
            Tool name (e.g., get_accounts)
        """
        # Remove 'Handler' suffix if present
        if class_name.endswith('Handler'):
            class_name = class_name[:-7]

        # Convert CamelCase to snake_case
        result = []
        for i, char in enumerate(class_name):
            if i > 0 and char.isupper():
                result.append('_')
            result.append(char.lower())

        return ''.join(result)


# Global handler factory instance
_global_factory: Optional[HandlerFactory] = None


def get_handler_factory() -> HandlerFactory:
    """Get the global handler factory instance.

    Returns:
        Global HandlerFactory instance
    """
    global _global_factory
    if _global_factory is None:
        _global_factory = HandlerFactory()
    return _global_factory