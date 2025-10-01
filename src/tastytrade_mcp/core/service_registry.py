"""Service registry for dependency injection."""
from typing import Any, Dict, Optional, Type, TypeVar
from tastytrade_mcp.utils.logging import get_logger

T = TypeVar('T')
logger = get_logger(__name__)


class ServiceNotFoundError(Exception):
    """Exception raised when a service is not found in the registry."""
    pass


class ServiceRegistry:
    """Central service registry for dependency injection.

    This registry provides a centralized location for managing
    service instances that can be injected into handlers.
    """

    def __init__(self):
        """Initialize the service registry."""
        self._services: Dict[str, Any] = {}
        self._service_types: Dict[str, Type] = {}
        self.logger = logger

    def register(self, name: str, service: Any, service_type: Optional[Type] = None) -> None:
        """Register a service in the registry.

        Args:
            name: Service name/identifier
            service: Service instance
            service_type: Optional type hint for the service
        """
        if name in self._services:
            self.logger.warning(f"Overwriting existing service: {name}")

        self._services[name] = service
        if service_type:
            self._service_types[name] = service_type

        self.logger.debug(f"Registered service: {name}")

    def get(self, name: str, required: bool = True) -> Any:
        """Get a service from the registry.

        Args:
            name: Service name/identifier
            required: If True, raise exception if not found

        Returns:
            Service instance or None if not found and not required

        Raises:
            ServiceNotFoundError: If service not found and required=True
        """
        service = self._services.get(name)

        if service is None and required:
            available = ", ".join(self._services.keys())
            raise ServiceNotFoundError(
                f"Service '{name}' not found. Available services: {available}"
            )

        return service

    def get_typed(self, name: str, expected_type: Type[T]) -> T:
        """Get a typed service from the registry.

        Args:
            name: Service name/identifier
            expected_type: Expected type of the service

        Returns:
            Service instance with proper typing

        Raises:
            ServiceNotFoundError: If service not found
            TypeError: If service type doesn't match expected type
        """
        service = self.get(name, required=True)

        if not isinstance(service, expected_type):
            actual_type = type(service).__name__
            expected_name = expected_type.__name__
            raise TypeError(
                f"Service '{name}' is of type {actual_type}, expected {expected_name}"
            )

        return service

    def has(self, name: str) -> bool:
        """Check if a service is registered.

        Args:
            name: Service name/identifier

        Returns:
            True if service is registered
        """
        return name in self._services

    def unregister(self, name: str) -> None:
        """Remove a service from the registry.

        Args:
            name: Service name/identifier
        """
        if name in self._services:
            del self._services[name]
            if name in self._service_types:
                del self._service_types[name]
            self.logger.debug(f"Unregistered service: {name}")

    def clear(self) -> None:
        """Clear all services from the registry."""
        self._services.clear()
        self._service_types.clear()
        self.logger.debug("Cleared all services from registry")

    def list_services(self) -> Dict[str, str]:
        """List all registered services with their types.

        Returns:
            Dictionary mapping service names to type names
        """
        result = {}
        for name, service in self._services.items():
            if name in self._service_types:
                type_name = self._service_types[name].__name__
            else:
                type_name = type(service).__name__
            result[name] = type_name
        return result

    async def initialize_services(self) -> None:
        """Initialize all registered services that have an init method.

        This is useful for services that need async initialization.
        """
        for name, service in self._services.items():
            if hasattr(service, 'initialize') and callable(getattr(service, 'initialize')):
                self.logger.debug(f"Initializing service: {name}")
                await service.initialize()

    async def cleanup_services(self) -> None:
        """Clean up all registered services that have a cleanup method.

        This is useful for properly closing connections, etc.
        """
        for name, service in self._services.items():
            if hasattr(service, 'cleanup') and callable(getattr(service, 'cleanup')):
                self.logger.debug(f"Cleaning up service: {name}")
                try:
                    await service.cleanup()
                except Exception as e:
                    self.logger.error(f"Error cleaning up service {name}: {e}")


# Global service registry instance
_global_registry: Optional[ServiceRegistry] = None


def get_service_registry() -> ServiceRegistry:
    """Get the global service registry instance.

    Returns:
        Global ServiceRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ServiceRegistry()
    return _global_registry