"""
Database setup and initialization utilities for TastyTrade MCP Server

This module handles:
1. Clean database initialization (no user data)
2. Database migration management
3. Initial user seeding for database mode
4. Database health checks
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from tastytrade_mcp.db.engine import get_engine, init_db
from tastytrade_mcp.db.session import get_session_context
from tastytrade_mcp.db.base import Base
from tastytrade_mcp.models.auth import BrokerLink, BrokerSecret, LinkStatus
from tastytrade_mcp.models.user import User, UserStatus
from tastytrade_mcp.services.encryption import EncryptionService

logger = logging.getLogger(__name__)


class DatabaseSetupError(Exception):
    """Database setup related errors"""
    pass


async def clean_database_init(database_path: Optional[Path] = None) -> bool:
    """
    Initialize a clean database with no user data.

    This creates all tables but does NOT populate them with any user-specific data.
    Perfect for distribution - users will add their own data during setup.

    Args:
        database_path: Optional path for SQLite database

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Initializing clean database (no user data)...")

        # Remove existing database file if it exists (for SQLite)
        if database_path and database_path.exists():
            logger.info(f"Removing existing database: {database_path}")
            database_path.unlink()

        # Initialize database schema
        await init_db()

        # Verify tables were created
        engine = get_engine()
        async with engine.begin() as conn:
            # Check if core tables exist
            result = await conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('users', 'broker_links', 'broker_secrets')"
            ))
            tables = [row[0] for row in result.fetchall()]

            if len(tables) >= 3:
                logger.info(f"✓ Database initialized with {len(tables)} tables")
                return True
            else:
                logger.error(f"Database initialization incomplete. Found tables: {tables}")
                return False

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False


async def seed_initial_user(
    user_id: Optional[str] = None,
    refresh_token: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    is_sandbox: bool = True
) -> Optional[str]:
    """
    Seed the database with an initial user and encrypted OAuth tokens.

    This is called during CLI setup when a user provides personal grant credentials.

    Args:
        user_id: Optional user ID (generates UUID if not provided)
        refresh_token: OAuth refresh token from personal grant
        client_id: OAuth client ID (stored in env, not database)
        client_secret: OAuth client secret (stored in env, not database)
        is_sandbox: Whether tokens are for sandbox environment

    Returns:
        str: User ID if successful, None if failed
    """
    try:
        if not refresh_token:
            raise DatabaseSetupError("Refresh token is required for user seeding")

        user_uuid = uuid.uuid4() if not user_id else uuid.UUID(user_id)

        async with get_session_context() as session:
            # Create user
            user = User(
                id=user_uuid,
                email=f"user_{user_uuid.hex[:8]}@tastytrade-mcp.local",
                status=UserStatus.ACTIVE,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(user)
            await session.flush()

            # Use OAuthService to setup personal grant
            # This will validate the refresh token and get initial access token
            from tastytrade_mcp.auth.oauth_service import OAuthService

            oauth_service = OAuthService(session)
            broker_link = await oauth_service.setup_personal_grant(
                user_id=user.id,
                refresh_token=refresh_token,
                is_sandbox=is_sandbox
            )

            logger.info(f"✓ Seeded initial user: {user.id}")
            return str(user.id)

    except Exception as e:
        logger.error(f"User seeding failed: {e}")
        return None


async def check_database_health() -> dict:
    """
    Check database health and return status information.

    Returns:
        dict: Health status with tables, user count, etc.
    """
    try:
        engine = get_engine()
        health_info = {
            "status": "healthy",
            "tables": [],
            "user_count": 0,
            "broker_links_count": 0,
            "errors": []
        }

        async with engine.begin() as conn:
            # Check tables
            try:
                result = await conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ))
                health_info["tables"] = [row[0] for row in result.fetchall()]
            except Exception as e:
                health_info["errors"].append(f"Table check failed: {e}")

            # Check user count
            try:
                result = await conn.execute(text("SELECT COUNT(*) FROM users"))
                health_info["user_count"] = result.fetchone()[0]
            except Exception as e:
                health_info["errors"].append(f"User count failed: {e}")

            # Check broker links
            try:
                result = await conn.execute(text("SELECT COUNT(*) FROM broker_links"))
                health_info["broker_links_count"] = result.fetchone()[0]
            except Exception as e:
                health_info["errors"].append(f"Broker links count failed: {e}")

        if health_info["errors"]:
            health_info["status"] = "warning"

        return health_info

    except Exception as e:
        return {
            "status": "error",
            "tables": [],
            "user_count": 0,
            "broker_links_count": 0,
            "errors": [f"Database connection failed: {e}"]
        }


async def cleanup_database() -> bool:
    """
    Clean up database (remove all user data but keep schema).

    This is useful for development/testing.

    Returns:
        bool: True if successful
    """
    try:
        logger.info("Cleaning up database (removing all user data)...")

        async with get_session_context() as session:
            # Delete in correct order (respecting foreign keys)
            await session.execute(text("DELETE FROM broker_secrets"))
            await session.execute(text("DELETE FROM broker_links"))
            await session.execute(text("DELETE FROM oauth_states"))
            await session.execute(text("DELETE FROM users"))

            await session.commit()

        logger.info("✓ Database cleanup completed")
        return True

    except Exception as e:
        logger.error(f"Database cleanup failed: {e}")
        return False


async def migrate_database() -> bool:
    """
    Run database migrations (placeholder for future migrations).

    Returns:
        bool: True if successful
    """
    try:
        logger.info("Running database migrations...")

        # For now, just ensure all tables exist
        await init_db()

        logger.info("✓ Database migrations completed")
        return True

    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        return False


# CLI helper functions
async def setup_database_mode(
    refresh_token: str,
    client_id: str,
    client_secret: str,
    is_sandbox: bool = True,
    database_path: Optional[Path] = None
) -> Optional[str]:
    """
    Complete database mode setup: clean init + user seeding.

    This is the main function called by the CLI during database mode setup.

    Args:
        refresh_token: OAuth refresh token
        client_id: OAuth client ID
        client_secret: OAuth client secret
        is_sandbox: Whether using sandbox environment
        database_path: Optional database path for SQLite

    Returns:
        str: User ID if successful, None if failed
    """
    try:
        # Step 1: Clean database initialization
        if not await clean_database_init(database_path):
            raise DatabaseSetupError("Failed to initialize clean database")

        # Step 2: Seed initial user with OAuth tokens
        user_id = await seed_initial_user(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            is_sandbox=is_sandbox
        )

        if not user_id:
            raise DatabaseSetupError("Failed to seed initial user")

        # Step 3: Health check
        health = await check_database_health()
        if health["status"] == "error":
            raise DatabaseSetupError(f"Database health check failed: {health['errors']}")

        logger.info(f"✓ Database mode setup complete. User ID: {user_id}")
        return user_id

    except Exception as e:
        logger.error(f"Database mode setup failed: {e}")
        return None


if __name__ == "__main__":
    # Example usage for testing
    async def main():
        # Test clean database initialization
        result = await clean_database_init()
        logger.info(f"Clean init result: {result}")

        # Test health check
        health = await check_database_health()
        logger.info(f"Health check: {health}")

    asyncio.run(main())