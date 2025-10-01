"""Helper functions for API routes."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tastytrade_mcp.models.auth import BrokerLink, LinkStatus
from tastytrade_mcp.models.user import User


async def get_active_broker_link(
    session: AsyncSession,
    user: User
) -> BrokerLink | None:
    """Get active broker link for a user.

    Args:
        session: Database session
        user: User object

    Returns:
        Active broker link or None if not found
    """
    result = await session.execute(
        select(BrokerLink)
        .where(BrokerLink.user_id == user.id)
        .where(BrokerLink.status == LinkStatus.ACTIVE)
    )
    return result.scalar_one_or_none()