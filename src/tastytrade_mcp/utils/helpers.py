"""Helper utility functions."""
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tastytrade_mcp.models.auth import BrokerLink, LinkStatus
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger("helpers")


async def get_broker_link(session: AsyncSession, user_id: str) -> BrokerLink | None:
    """Get active broker link for a user."""
    try:
        # Parse user_id as UUID
        user_uuid = UUID(user_id)

        # Query for active broker link
        result = await session.execute(
            select(BrokerLink)
            .where(BrokerLink.user_id == user_uuid)
            .where(BrokerLink.status == LinkStatus.ACTIVE)
        )
        return result.scalar_one_or_none()
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid user_id format: {user_id} - {e}")
        return None