"""Market data models."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tastytrade_mcp.db.base import Base, get_timestamp_column, get_uuid_column


class WSEntitlement(Base):
    """WebSocket entitlement for market data streaming."""
    
    __tablename__ = "ws_entitlements"
    
    id: Mapped[uuid.UUID] = get_uuid_column()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    account_number: Mapped[str] = mapped_column(String(50), nullable=False)
    entitlement_level: Mapped[Optional[str]] = mapped_column(String(50))
    token: Mapped[str] = mapped_column(Text, nullable=False)
    dxlink_url: Mapped[Optional[str]] = mapped_column(Text)
    issued_at: Mapped[datetime] = get_timestamp_column()
    expires_at: Mapped[datetime] = get_timestamp_column()