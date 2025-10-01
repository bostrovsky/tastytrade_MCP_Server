"""Database base configuration."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""
    
    # This allows us to use native PostgreSQL types when available
    type_annotation_map = {
        uuid.UUID: UUID(as_uuid=True),
    }


def get_uuid_column() -> Mapped[uuid.UUID]:
    """
    Get a UUID column that works with both PostgreSQL and SQLite.
    
    PostgreSQL: Uses native UUID type
    SQLite: Uses String(36) with Python UUID conversion
    """
    import os
    database_url = os.getenv("DATABASE_URL", "")
    
    if "sqlite" in database_url:
        # For SQLite/testing, use String
        return mapped_column(
            String(36),
            primary_key=True,
            default=lambda: str(uuid.uuid4()),
            nullable=False
        )
    else:
        # For PostgreSQL, use native UUID
        return mapped_column(
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
            server_default=func.gen_random_uuid(),
            nullable=False
        )


def get_timestamp_column(nullable: bool = False) -> Mapped[datetime]:
    """
    Get a timestamp column that works with both databases.
    """
    return mapped_column(
        DateTime(timezone=True),
        nullable=nullable,
        server_default=func.now() if not nullable else None
    )