"""Authentication and authorization models."""
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tastytrade_mcp.db.base import Base, get_timestamp_column, get_uuid_column


class LinkStatus(str, enum.Enum):
    """Broker link status."""
    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class BrokerLink(Base):
    """Broker link model."""
    
    __tablename__ = "broker_links"
    
    id: Mapped[uuid.UUID] = get_uuid_column()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), default="tastytrade")
    account_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_sandbox: Mapped[bool] = mapped_column(default=True, nullable=False)
    scope: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[LinkStatus] = mapped_column(
        Enum(LinkStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]),
        default=LinkStatus.PENDING,
        nullable=False
    )
    linked_at: Mapped[datetime] = get_timestamp_column()
    revoked_at: Mapped[Optional[datetime]] = get_timestamp_column(nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="broker_links")
    secrets: Mapped[list["BrokerSecret"]] = relationship(
        back_populates="broker_link",
        cascade="all, delete-orphan"
    )

    @property
    def broker_secret(self):
        """Get the first (and usually only) broker secret."""
        return self.secrets[0] if self.secrets else None

    @broker_secret.setter
    def broker_secret(self, value):
        """Set the broker secret."""
        if value:
            self.secrets = [value]
        else:
            self.secrets = []


class BrokerSecret(Base):
    """Encrypted broker secrets (tokens)."""
    
    __tablename__ = "broker_secrets"
    
    id: Mapped[uuid.UUID] = get_uuid_column()
    broker_link_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("broker_links.id", ondelete="CASCADE"),
        nullable=False
    )
    enc_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    enc_refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    access_expires_at: Mapped[datetime] = get_timestamp_column()
    refresh_expires_at: Mapped[Optional[datetime]] = get_timestamp_column(nullable=True)
    created_at: Mapped[datetime] = get_timestamp_column()
    updated_at: Mapped[datetime] = get_timestamp_column()
    
    # Relationships
    broker_link: Mapped["BrokerLink"] = relationship(back_populates="secrets")


class OAuthState(Base):
    """OAuth state for authorization flow."""
    
    __tablename__ = "oauth_states"
    
    id: Mapped[uuid.UUID] = get_uuid_column()
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True
    )
    state: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    code_verifier_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    redirect_uri: Mapped[Optional[str]] = mapped_column(Text)
    is_sandbox: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = get_timestamp_column()
    expires_at: Mapped[datetime] = get_timestamp_column()