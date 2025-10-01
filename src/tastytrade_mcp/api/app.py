"""FastAPI application for TastyTrade MCP Server."""
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from tastytrade_mcp.api.health import router as health_router
from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.db.session import close_database, init_database
from tastytrade_mcp.services.cache import get_cache
from tastytrade_mcp.services.encryption import get_encryption_service
from tastytrade_mcp.utils.logging import get_logger, log_request, setup_logging

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.
    Initialize resources on startup, cleanup on shutdown.
    """
    # Startup
    logger.info("Starting TastyTrade MCP Server")
    
    # Set up logging
    setup_logging()
    
    # Initialize database
    await init_database()
    logger.info("Database initialized")
    
    # Initialize cache
    cache = await get_cache()
    logger.info("Cache service initialized")
    
    # Initialize encryption
    encryption = await get_encryption_service()
    logger.info("Encryption service initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down TastyTrade MCP Server")
    
    # Close database connections
    await close_database()
    
    # Close cache connections
    if cache:
        await cache.close()
    
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    # Load OpenAPI description
    description = """
Model Context Protocol server for TastyTrade API integration with comprehensive safety measures.

## Features
- 🔐 OAuth2 authentication with TastyTrade
- 📊 Real-time market data streaming
- 💼 Portfolio and position management
- 📈 Two-step trade confirmation flow
- 🔒 Encrypted token storage
- 🏖️ Sandbox mode for testing
- 📝 Comprehensive audit logging

## Safety Measures
- Two-step confirmation for all trades
- Token encryption at rest
- Rate limiting and position limits
- Audit trail for all operations
- Sandbox environment for testing

## Getting Started
1. Initiate OAuth flow at `/auth/oauth/initiate`
2. Complete authentication with TastyTrade
3. Use the returned JWT token for API access
4. Start with `/market/search` to find symbols
5. Preview trades with `/trading/preview`
    """
    
    app = FastAPI(
        title="TastyTrade MCP Server",
        description=description,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_tags=[
            {"name": "Health", "description": "Health check and monitoring endpoints"},
            {"name": "Authentication", "description": "OAuth2 authentication flow"},
            {"name": "Market Data", "description": "Real-time market data and quotes"},
            {"name": "Trading", "description": "Order management and execution"},
            {"name": "Account", "description": "Account information and positions"},
        ],
        contact={
            "name": "TastyTrade MCP Team",
            "email": "support@tastytrade-mcp.local",
        },
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log all HTTP requests."""
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log request
        log_request(
            logger,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            client=request.client.host if request.client else None,
        )
        
        # Add response headers
        response.headers["X-Process-Time"] = str(duration_ms)
        response.headers["X-Version"] = settings.app_version
        
        return response
    
    # Add exception handlers
    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        """Handle 404 errors."""
        return JSONResponse(
            status_code=404,
            content={
                "error": "Not Found",
                "message": f"Path {request.url.path} not found",
            }
        )
    
    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc):
        """Handle 500 errors."""
        logger.error(f"Internal server error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred",
            }
        )
    
    # Root endpoint
    @app.get("/", response_model=Dict[str, Any])
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "TastyTrade MCP Server",
            "version": settings.app_version,
            "environment": settings.environment,
            "documentation": "/docs" if settings.debug else None,
        }
    
    # Include routers
    app.include_router(health_router)

    # Authentication router
    from tastytrade_mcp.api.auth import router as auth_router
    app.include_router(auth_router)

    # Accounts router
    from tastytrade_mcp.api.accounts import router as accounts_router
    app.include_router(accounts_router)

    # Positions router
    from tastytrade_mcp.api.positions import router as positions_router
    app.include_router(positions_router)

    # Balances router
    from tastytrade_mcp.api.balances import router as balances_router
    app.include_router(balances_router)

    # Market Data router
    from tastytrade_mcp.api.market_data import router as market_data_router
    app.include_router(market_data_router)

    # Orders router
    from tastytrade_mcp.api.orders import router as orders_router
    app.include_router(orders_router)

    # Future routers will be added here:
    # app.include_router(webhook_router)
    
    return app


# Create app instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)