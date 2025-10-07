"""Database engine configuration with PostgreSQL/SQLite support."""
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tastytrade_mcp.config.settings import get_settings


# Global engine and session factory
_engine = None
_async_session_factory = None


def get_engine():
    """Get or create the database engine."""
    global _engine

    if _engine is None:
        settings = get_settings()
        database_url = settings.database_url

        # Default to SQLite if no DATABASE_URL is set
        if not database_url:
            database_url = "sqlite+aiosqlite:///./tastytrade_mcp.db"

        # Determine if we're using SQLite or PostgreSQL
        is_sqlite = "sqlite" in database_url
        
        if is_sqlite:
            # SQLite configuration
            connect_args = {"check_same_thread": False}
            _engine = create_async_engine(
                database_url,
                connect_args=connect_args,
                echo=settings.debug,
                poolclass=NullPool,  # SQLite doesn't handle connection pooling well
            )
        else:
            # PostgreSQL configuration
            _engine = create_async_engine(
                database_url,
                echo=settings.debug,
                pool_pre_ping=True,  # Verify connections before using
                pool_size=5,
                max_overflow=10,
            )
    
    return _engine


def get_session_factory():
    """Get or create the session factory."""
    global _async_session_factory
    
    if _async_session_factory is None:
        engine = get_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    return _async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session for internal use.
    
    This is the actual implementation that creates sessions.
    """
    async_session = get_session_factory()
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize the database (create tables if they don't exist)."""
    from tastytrade_mcp.db.base import Base
    from tastytrade_mcp.models import (  # Import all models to register them
        User, BrokerLink, BrokerSecret, OAuthState,
        OrderPreview, OrderAudit, UserSubscription, WSEntitlement
    )
    
    engine = get_engine()
    
    async with engine.begin() as conn:
        # For development, create tables if they don't exist
        # In production, use Alembic migrations instead
        if get_settings().environment == "development":
            await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    global _engine
    
    if _engine is not None:
        await _engine.dispose()
        _engine = None