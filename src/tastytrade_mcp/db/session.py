"""Database session management."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tastytrade_mcp.db.engine import get_engine


async def init_database() -> None:
    """Initialize database connection."""
    engine = get_engine()
    # Test connection
    from sqlalchemy import text as sql_text
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: c.execute(sql_text("SELECT 1")))


async def close_database() -> None:
    """Close database connections."""
    engine = get_engine()
    await engine.dispose()


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Get async database session as context manager.
    
    Usage:
        async with get_session_context() as session:
            result = await session.execute(query)
    """
    engine = get_engine()
    async with AsyncSession(engine) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get async database session for FastAPI dependency.
    
    Usage in FastAPI:
        session: AsyncSession = Depends(get_session)
    """
    from tastytrade_mcp.db.engine import get_db_session
    async for session in get_db_session():
        yield session