"""Base handler class for all MCP tool handlers."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
import logging

import mcp.types as types
from sqlalchemy.ext.asyncio import AsyncSession

from tastytrade_mcp.services.tastytrade import TastyTradeService
from tastytrade_mcp.utils.logging import get_logger


class HandlerError(Exception):
    """Base exception for handler errors."""

    def __init__(self, message: str, code: str = "HANDLER_ERROR", details: Optional[Dict] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)


class ValidationError(HandlerError):
    """Exception for validation errors."""

    def __init__(self, message: str, field: Optional[str] = None):
        details = {"field": field} if field else {}
        super().__init__(message, "VALIDATION_ERROR", details)


class ServiceError(HandlerError):
    """Exception for service-level errors."""

    def __init__(self, message: str, service: Optional[str] = None):
        details = {"service": service} if service else {}
        super().__init__(message, "SERVICE_ERROR", details)


class BaseHandler(ABC):
    """Base class for all MCP tool handlers.

    This class provides:
    - Common initialization with service and session
    - Standard validation, execution, and formatting flow
    - Error handling and logging
    - Response formatting utilities
    """

    def __init__(
        self,
        service: Optional[TastyTradeService] = None,
        session: Optional[AsyncSession] = None,
        logger: Optional[logging.Logger] = None
    ):
        """Initialize handler with dependencies.

        Args:
            service: TastyTrade service instance
            session: Database session
            logger: Logger instance (creates one if not provided)
        """
        self.service = service
        self.session = session
        self.logger = logger or get_logger(self.__class__.__name__)

    async def handle(self, arguments: Dict[str, Any]) -> List[types.TextContent]:
        """Main entry point for handling requests.

        Implements the standard flow:
        1. Validate request
        2. Execute business logic
        3. Format response
        4. Handle errors

        Args:
            arguments: Request arguments from MCP

        Returns:
            Formatted response as list of TextContent
        """
        try:
            # Validate request
            await self.validate_request(arguments)

            # Execute handler logic
            data = await self.execute(arguments)

            # Format and return response
            return await self.format_response(data)

        except HandlerError as e:
            self.logger.warning(f"Handler error: {e.code} - {e.message}", extra=e.details)
            return self._error_response(e.message, e.code)

        except Exception as e:
            self.logger.error(f"Unexpected error in {self.__class__.__name__}: {e}", exc_info=True)
            return self._error_response("An unexpected error occurred", "INTERNAL_ERROR")

    async def validate_request(self, arguments: Dict[str, Any]) -> None:
        """Validate request arguments.

        Override this method to implement specific validation logic.
        Raise ValidationError for validation failures.

        Args:
            arguments: Request arguments to validate
        """
        pass

    @abstractmethod
    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute the handler's business logic.

        This method must be implemented by all handlers.

        Args:
            arguments: Validated request arguments

        Returns:
            Data to be formatted for response
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement execute method"
        )

    async def format_response(self, data: Any) -> List[types.TextContent]:
        """Format data into MCP response.

        Override this method to implement custom formatting.
        Default implementation converts data to string.

        Args:
            data: Data from execute method

        Returns:
            Formatted response as list of TextContent
        """
        return [types.TextContent(type="text", text=str(data))]

    def _error_response(self, message: str, code: str = "ERROR") -> List[types.TextContent]:
        """Create standardized error response.

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

    def _success_response(self, message: str) -> List[types.TextContent]:
        """Create standardized success response.

        Args:
            message: Success message

        Returns:
            Success response as list of TextContent
        """
        return [
            types.TextContent(
                type="text",
                text=f"✅ {message}"
            )
        ]

    def require_service(self) -> TastyTradeService:
        """Get service instance, raising error if not available.

        Returns:
            TastyTrade service instance

        Raises:
            ServiceError: If service is not available
        """
        if not self.service:
            raise ServiceError("TastyTrade service not available")
        return self.service

    def require_session(self) -> AsyncSession:
        """Get session instance, raising error if not available.

        Returns:
            Database session instance

        Raises:
            ServiceError: If session is not available
        """
        if not self.session:
            raise ServiceError("Database session not available")
        return self.session

    def validate_required_field(
        self,
        arguments: Dict[str, Any],
        field: str,
        field_type: Optional[Type] = None
    ) -> Any:
        """Validate that a required field exists and has correct type.

        Args:
            arguments: Request arguments
            field: Field name to validate
            field_type: Expected type (optional)

        Returns:
            Field value

        Raises:
            ValidationError: If field is missing or has wrong type
        """
        if field not in arguments:
            raise ValidationError(f"Required field '{field}' is missing", field)

        value = arguments[field]

        if field_type and not isinstance(value, field_type):
            raise ValidationError(
                f"Field '{field}' must be of type {field_type.__name__}",
                field
            )

        return value