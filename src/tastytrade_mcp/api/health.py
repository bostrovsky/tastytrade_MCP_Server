"""Health check endpoints for monitoring and operations."""
import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.db.session import get_session_context
from tastytrade_mcp.services.cache import get_cache
from tastytrade_mcp.utils.logging import get_logger

router = APIRouter(prefix="/health", tags=["health"])
logger = get_logger(__name__)
settings = get_settings()

# Track application start time
APP_START_TIME = datetime.utcnow()


class HealthStatus(BaseModel):
    """Health check status."""
    status: str
    timestamp: datetime
    uptime_seconds: float
    version: str
    environment: str


class ComponentHealth(BaseModel):
    """Individual component health."""
    name: str
    status: str
    response_time_ms: Optional[float] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DetailedHealth(BaseModel):
    """Detailed health check response."""
    status: str
    timestamp: datetime
    uptime_seconds: float
    version: str
    environment: str
    components: List[ComponentHealth]


async def check_database() -> ComponentHealth:
    """Check database connectivity and performance."""
    start_time = time.time()
    
    try:
        async with get_session_context() as session:
            # Execute a simple query
            result = await session.execute(text("SELECT 1"))
            result.scalar()
            
            # Check if migrations are up to date
            try:
                result = await session.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                )
                migration_version = result.scalar()
                metadata = {"migration_version": migration_version}
            except Exception:
                metadata = {"migration_version": "unknown"}
            
        response_time = (time.time() - start_time) * 1000
        
        return ComponentHealth(
            name="database",
            status="healthy",
            response_time_ms=response_time,
            message="Database connection successful",
            metadata=metadata
        )
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"Database health check failed: {e}")
        
        return ComponentHealth(
            name="database",
            status="unhealthy",
            response_time_ms=response_time,
            message=f"Database connection failed: {str(e)}"
        )


async def check_redis() -> ComponentHealth:
    """Check Redis connectivity and performance."""
    start_time = time.time()
    
    try:
        cache = await get_cache()
        
        # Test basic operations
        test_key = "health_check_test"
        test_value = str(datetime.utcnow().timestamp())
        
        # Set a value
        await cache.set(test_key, test_value, ttl=10)
        
        # Get the value back
        retrieved = await cache.get(test_key)
        
        # Clean up
        await cache.delete(test_key)
        
        if retrieved != test_value:
            raise ValueError("Cache read/write mismatch")
        
        response_time = (time.time() - start_time) * 1000
        
        # Determine if using Redis or in-memory
        cache_type = "redis" if settings.use_redis else "in-memory"
        
        return ComponentHealth(
            name="cache",
            status="healthy",
            response_time_ms=response_time,
            message=f"Cache ({cache_type}) operational",
            metadata={"type": cache_type}
        )
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"Cache health check failed: {e}")
        
        return ComponentHealth(
            name="cache",
            status="degraded",
            response_time_ms=response_time,
            message=f"Cache check failed: {str(e)}",
            metadata={"fallback": "in-memory"}
        )


async def check_tastytrade_api() -> ComponentHealth:
    """Check TastyTrade API connectivity."""
    start_time = time.time()
    
    try:
        import httpx
        
        # Just check if the API endpoint is reachable
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.tastytrade_base_url}/",
                timeout=5.0
            )
            
            response_time = (time.time() - start_time) * 1000
            
            if response.status_code < 500:
                return ComponentHealth(
                    name="tastytrade_api",
                    status="healthy",
                    response_time_ms=response_time,
                    message="TastyTrade API reachable",
                    metadata={
                        "base_url": settings.tastytrade_base_url,
                        "sandbox": settings.use_sandbox
                    }
                )
            else:
                return ComponentHealth(
                    name="tastytrade_api",
                    status="degraded",
                    response_time_ms=response_time,
                    message=f"TastyTrade API returned {response.status_code}",
                    metadata={"status_code": response.status_code}
                )
    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"TastyTrade API health check failed: {e}")
        
        return ComponentHealth(
            name="tastytrade_api",
            status="unhealthy",
            response_time_ms=response_time,
            message=f"TastyTrade API unreachable: {str(e)}"
        )


@router.get("/", response_model=HealthStatus)
async def health_check() -> HealthStatus:
    """
    Basic health check endpoint.
    Returns 200 if the service is running.
    """
    uptime = (datetime.utcnow() - APP_START_TIME).total_seconds()
    
    return HealthStatus(
        status="healthy",
        timestamp=datetime.utcnow(),
        uptime_seconds=uptime,
        version=settings.app_version,
        environment=settings.environment
    )


@router.get("/live", response_model=Dict[str, str])
async def liveness_probe() -> Dict[str, str]:
    """
    Kubernetes liveness probe endpoint.
    Returns 200 if the service is alive.
    """
    return {"status": "alive"}


@router.get("/ready", response_model=Dict[str, str])
async def readiness_probe() -> Dict[str, str]:
    """
    Kubernetes readiness probe endpoint.
    Returns 200 if the service is ready to accept traffic.
    Returns 503 if any critical component is unhealthy.
    """
    # Check critical components
    checks = await asyncio.gather(
        check_database(),
        return_exceptions=True
    )
    
    # Database is critical
    db_check = checks[0]
    if isinstance(db_check, Exception) or db_check.status == "unhealthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready: Database unavailable"
        )
    
    return {"status": "ready"}


@router.get("/detailed", response_model=DetailedHealth)
async def detailed_health_check() -> DetailedHealth:
    """
    Detailed health check with component status.
    Checks all service dependencies.
    """
    uptime = (datetime.utcnow() - APP_START_TIME).total_seconds()
    
    # Run all health checks in parallel
    component_checks = await asyncio.gather(
        check_database(),
        check_redis(),
        check_tastytrade_api(),
        return_exceptions=True
    )
    
    # Process results
    components = []
    overall_status = "healthy"
    
    for check in component_checks:
        if isinstance(check, Exception):
            # If check failed with exception
            components.append(
                ComponentHealth(
                    name="unknown",
                    status="error",
                    message=str(check)
                )
            )
            overall_status = "unhealthy"
        else:
            components.append(check)
            if check.status == "unhealthy":
                overall_status = "unhealthy"
            elif check.status == "degraded" and overall_status == "healthy":
                overall_status = "degraded"
    
    return DetailedHealth(
        status=overall_status,
        timestamp=datetime.utcnow(),
        uptime_seconds=uptime,
        version=settings.app_version,
        environment=settings.environment,
        components=components
    )


@router.get("/metrics", response_model=Dict[str, Any])
async def metrics() -> Dict[str, Any]:
    """
    Basic metrics endpoint for monitoring.
    In production, this would integrate with Prometheus/DataDog.
    """
    uptime = (datetime.utcnow() - APP_START_TIME).total_seconds()
    
    # Collect basic metrics
    metrics_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": uptime,
        "version": settings.app_version,
        "environment": settings.environment,
        "process": {
            "memory_usage_mb": 0,  # Would use psutil in production
            "cpu_percent": 0,       # Would use psutil in production
        },
        "application": {
            "total_requests": 0,    # Would track in middleware
            "active_connections": 0, # Would track WebSocket connections
            "error_rate": 0.0,      # Would calculate from logs
        }
    }
    
    # In production, would collect real metrics from:
    # - Database connection pool
    # - Redis connection pool
    # - Request/response times
    # - Error rates
    # - Business metrics (orders, authentications, etc.)
    
    return metrics_data