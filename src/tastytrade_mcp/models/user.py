"""User models."""
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tastytrade_mcp.db.base import Base, get_timestamp_column, get_uuid_column


class UserStatus(str, enum.Enum):
    """User account status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class SubscriptionStatus(str, enum.Enum):
    """Subscription status."""
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    INCOMPLETE = "incomplete"


class User(Base):
    """User model."""
    
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = get_uuid_column()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]),
        default=UserStatus.ACTIVE,
        nullable=False
    )
    is_free_access: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = get_timestamp_column()
    updated_at: Mapped[datetime] = get_timestamp_column()
    
    # Relationships
    broker_links: Mapped[list["BrokerLink"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["UserSubscription"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )


class UserSubscription(Base):
    """User subscription model."""
    
    __tablename__ = "user_subscriptions"
    
    id: Mapped[uuid.UUID] = get_uuid_column()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), default="stripe")
    subscription_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    customer_id: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False
    )
    plan_id: Mapped[Optional[str]] = mapped_column(String(100))
    current_period_start: Mapped[Optional[datetime]] = get_timestamp_column(nullable=True)
    current_period_end: Mapped[Optional[datetime]] = get_timestamp_column(nullable=True)
    trial_end: Mapped[Optional[datetime]] = get_timestamp_column(nullable=True)
    is_free_granted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = get_timestamp_column()
    updated_at: Mapped[datetime] = get_timestamp_column()
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="subscriptions")