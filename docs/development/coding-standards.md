# TastyTrade MCP Coding Standards

## Module Structure Requirements

### File Size Limits
- **Maximum lines per file**: 500 lines
- **Target lines per file**: 300-400 lines
- **Handler groups**: 6-8 handlers per module

### Module Organization
```
src/tastytrade_mcp/
├── core/
│   ├── __init__.py
│   ├── server.py          # MCP server setup (<500 lines)
│   ├── base_handler.py    # Base handler class
│   └── dispatcher.py      # Handler routing
├── handlers/
│   ├── __init__.py
│   ├── accounts.py        # Account management
│   ├── positions.py       # Position tracking
│   ├── trading.py         # Order operations
│   ├── market_data.py     # Market quotes
│   ├── options.py         # Options analysis
│   ├── risk.py           # Risk validation
│   └── system.py         # Health/emergency
└── main.py               # Entry point only
```

## Import Standards

### Import Order
1. Standard library imports
2. Third-party imports
3. Local application imports
4. Relative imports (avoid circular)

### Example:
```python
# Standard library
import asyncio
from typing import Any, Dict, List

# Third-party
import httpx
from mcp.server import Server

# Local application
from tastytrade_mcp.core.base_handler import BaseHandler
from tastytrade_mcp.services.tastytrade import TastyTradeService

# Relative (use sparingly)
from .utils import format_response
```

## Handler Implementation Pattern

### Base Handler Class
```python
class BaseHandler:
    """Base class for all MCP handlers."""

    def __init__(self, service: TastyTradeService, session: AsyncSession):
        self.service = service
        self.session = session
        self.logger = get_logger(self.__class__.__name__)

    async def validate_request(self, arguments: Dict[str, Any]) -> None:
        """Validate request arguments."""
        pass

    async def execute(self, arguments: Dict[str, Any]) -> Any:
        """Execute handler logic."""
        raise NotImplementedError

    async def format_response(self, data: Any) -> List[TextContent]:
        """Format response for MCP."""
        pass
```

### Handler Implementation
```python
class AccountHandler(BaseHandler):
    """Handles account-related operations."""

    async def get_accounts(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get all accounts."""
        await self.validate_request(arguments)
        data = await self.execute(arguments)
        return await self.format_response(data)
```

## Testing Requirements

### Test Coverage
- **Minimum coverage**: 80%
- **Handler coverage**: 100%
- **Integration tests**: Required for each handler group

### Test Structure
```
tests/
├── unit/
│   ├── test_base_handler.py
│   ├── handlers/
│   │   ├── test_accounts.py
│   │   ├── test_positions.py
│   │   └── ...
├── integration/
│   ├── test_mcp_server.py
│   └── test_handler_routing.py
└── fixtures/
    └── mock_data.py
```

### Test Example
```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_account_handler_get_accounts():
    """Test account retrieval."""
    # Arrange
    mock_service = AsyncMock()
    handler = AccountHandler(mock_service, None)

    # Act
    result = await handler.get_accounts({})

    # Assert
    assert result is not None
    mock_service.get_accounts.assert_called_once()
```

## Dependency Injection

### Service Registry
```python
class ServiceRegistry:
    """Central service registry."""

    def __init__(self):
        self._services = {}

    def register(self, name: str, service: Any):
        self._services[name] = service

    def get(self, name: str) -> Any:
        return self._services.get(name)
```

### Handler Factory
```python
class HandlerFactory:
    """Factory for creating handlers with dependencies."""

    def __init__(self, registry: ServiceRegistry):
        self.registry = registry

    def create_handler(self, handler_class: Type[BaseHandler]) -> BaseHandler:
        """Create handler with injected dependencies."""
        service = self.registry.get('tastytrade_service')
        session = self.registry.get('db_session')
        return handler_class(service, session)
```

## Error Handling

### Standard Error Response
```python
class HandlerError(Exception):
    """Base handler exception."""

    def __init__(self, message: str, code: str = "HANDLER_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)

async def handle_with_error_catch(handler_func):
    """Decorator for error handling."""
    try:
        return await handler_func()
    except HandlerError as e:
        return [TextContent(
            type="text",
            text=f"Error ({e.code}): {e.message}"
        )]
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return [TextContent(
            type="text",
            text="An unexpected error occurred"
        )]
```

## Migration Strategy

### Phase 1: Foundation (Current)
1. Create base handler class
2. Set up service registry
3. Create handler factory
4. Establish test framework

### Phase 2: Handler Extraction
1. Extract handler groups one at a time
2. Test each group independently
3. Integrate with dispatcher
4. Validate end-to-end

### Phase 3: Integration
1. Wire all handlers through dispatcher
2. Remove old monolithic code
3. Performance validation
4. Final testing

## Code Review Checklist

- [ ] File under 500 lines
- [ ] Imports properly ordered
- [ ] No circular dependencies
- [ ] Handler inherits from BaseHandler
- [ ] Unit tests written
- [ ] Integration tests written
- [ ] Error handling implemented
- [ ] Logging added
- [ ] Documentation updated
- [ ] Type hints complete