"""Order and trading-related models."""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, DateTime, Enum as SQLEnum, ForeignKey, Integer,
    JSON, Numeric, String, Text
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from tastytrade_mcp.db.base import Base


class OrderSide(str, Enum):
    """Order side enumeration."""
    BUY = "buy"
    SELL = "sell"
    BUY_TO_COVER = "buy_to_cover"
    SELL_SHORT = "sell_short"


class OrderType(str, Enum):
    """Order type enumeration."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForce(str, Enum):
    """Time in force enumeration."""
    DAY = "day"
    GTC = "gtc"  # Good Till Cancelled
    IOC = "ioc"  # Immediate Or Cancel
    FOK = "fok"  # Fill Or Kill
    GTD = "gtd"  # Good Till Date


class OrderStatus(str, Enum):
    """Order status enumeration."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    WORKING = "working"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderEventType(str, Enum):
    """Order event type enumeration."""
    CREATED = "created"
    PREVIEWED = "previewed"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    MODIFIED = "modified"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


# OrderPreview is defined in trading.py to avoid circular imports
class Order(Base):
    """Order model."""
    __tablename__ = "orders"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    external_order_id = Column(String(100), nullable=True, index=True)
    preview_token = Column(String(128), nullable=True)

    # Order details
    symbol = Column(String(50), nullable=False)
    side = Column(SQLEnum(OrderSide), nullable=False)
    quantity = Column(Integer, nullable=False)
    filled_quantity = Column(Integer, default=0)
    order_type = Column(SQLEnum(OrderType), nullable=False)
    price = Column(Numeric(10, 4), nullable=True)
    stop_price = Column(Numeric(10, 4), nullable=True)
    average_fill_price = Column(Numeric(10, 4), nullable=True)
    time_in_force = Column(SQLEnum(TimeInForce), default=TimeInForce.DAY)

    # Status
    status = Column(SQLEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING, index=True)

    # Timestamps
    submitted_at = Column(DateTime, nullable=True)
    filled_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancelled_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    events = relationship("OrderEvent", back_populates="order", cascade="all, delete-orphan")
    bracket_parent = relationship("BracketOrder", foreign_keys="BracketOrder.parent_order_id", back_populates="parent_order", uselist=False)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "account_id": str(self.account_id),
            "external_order_id": self.external_order_id,
            "symbol": self.symbol,
            "side": self.side.value if self.side else None,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "order_type": self.order_type.value if self.order_type else None,
            "price": float(self.price) if self.price else None,
            "stop_price": float(self.stop_price) if self.stop_price else None,
            "average_fill_price": float(self.average_fill_price) if self.average_fill_price else None,
            "time_in_force": self.time_in_force.value if self.time_in_force else None,
            "status": self.status.value if self.status else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "cancelled_reason": self.cancelled_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class OrderEvent(Base):
    """Order event model for audit trail."""
    __tablename__ = "order_events"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    order_id = Column(PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(SQLEnum(OrderEventType), nullable=False, index=True)
    event_data = Column(JSON, nullable=True)
    timestamp = Column(DateTime, server_default=func.now(), index=True)

    # Relationships
    order = relationship("Order", back_populates="events")

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "order_id": str(self.order_id),
            "event_type": self.event_type.value if self.event_type else None,
            "event_data": self.event_data,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class BracketOrder(Base):
    """Bracket order model for OCO (One-Cancels-Other) orders."""
    __tablename__ = "bracket_orders"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    parent_order_id = Column(PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    profit_target_order_id = Column(PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    stop_loss_order_id = Column(PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    parent_order = relationship("Order", foreign_keys=[parent_order_id], back_populates="bracket_parent")
    profit_target_order = relationship("Order", foreign_keys=[profit_target_order_id])
    stop_loss_order = relationship("Order", foreign_keys=[stop_loss_order_id])

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "parent_order_id": str(self.parent_order_id),
            "profit_target_order_id": str(self.profit_target_order_id) if self.profit_target_order_id else None,
            "stop_loss_order_id": str(self.stop_loss_order_id) if self.stop_loss_order_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }