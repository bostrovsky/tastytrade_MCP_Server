"""Trading and order models."""
import enum
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import JSON, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tastytrade_mcp.db.base import Base, get_timestamp_column, get_uuid_column


class OrderStatus(str, enum.Enum):
    """Order status."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SUBMITTED = "submitted"
    FAILED = "failed"


class OrderSide(str, enum.Enum):
    """Order side."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, enum.Enum):
    """Order type."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForce(str, enum.Enum):
    """Time in force."""
    DAY = "day"
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate or Cancel
    FOK = "fok"  # Fill or Kill


class OrderPreview(Base):
    """Order preview for two-step confirmation."""
    
    __tablename__ = "order_previews"
    
    id: Mapped[uuid.UUID] = get_uuid_column()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    account_number: Mapped[str] = mapped_column(String(50), nullable=False)
    order_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    estimated_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    nonce: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False),
        default=OrderStatus.PENDING,
        nullable=False
    )
    created_at: Mapped[datetime] = get_timestamp_column()
    expires_at: Mapped[datetime] = get_timestamp_column()
    confirmed_at: Mapped[Optional[datetime]] = get_timestamp_column(nullable=True)
    submitted_at: Mapped[Optional[datetime]] = get_timestamp_column(nullable=True)


class OrderAudit(Base):
    """Audit log for all order actions."""
    
    __tablename__ = "order_audits"
    
    id: Mapped[uuid.UUID] = get_uuid_column()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )
    account_number: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    payload_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    result_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = get_timestamp_column()