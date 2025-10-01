"""Sandbox trading environment models."""
import enum
import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, List

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text, DECIMAL, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tastytrade_mcp.db.base import Base, get_timestamp_column, get_uuid_column


class SandboxMode(str, enum.Enum):
    """Sandbox mode options."""
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class SandboxAccountStatus(str, enum.Enum):
    """Sandbox account status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    RESET_PENDING = "reset_pending"
    SUSPENDED = "suspended"


class SandboxOrderStatus(str, enum.Enum):
    """Sandbox order status."""
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class SandboxAccount(Base):
    """Sandbox trading account."""

    __tablename__ = "sandbox_accounts"

    id: Mapped[uuid.UUID] = get_uuid_column()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    account_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    nickname: Mapped[Optional[str]] = mapped_column(String(100))
    account_type: Mapped[str] = mapped_column(String(50), default="margin")
    status: Mapped[SandboxAccountStatus] = mapped_column(
        Enum(SandboxAccountStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]),
        default=SandboxAccountStatus.ACTIVE,
        nullable=False
    )

    # Initial setup values
    initial_balance: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal('100000.00'))
    current_balance: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal('100000.00'))
    buying_power: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal('200000.00'))
    net_liquidating_value: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal('100000.00'))

    # Risk settings
    day_trade_limit: Mapped[int] = mapped_column(Integer, default=3)
    position_limit: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal('50000.00'))

    # Educational features
    is_educational_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    show_sandbox_warnings: Mapped[bool] = mapped_column(Boolean, default=True)

    # Reset tracking
    reset_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reset_at: Mapped[Optional[datetime]] = get_timestamp_column(nullable=True)

    created_at: Mapped[datetime] = get_timestamp_column()
    updated_at: Mapped[datetime] = get_timestamp_column()

    # Relationships
    user: Mapped["User"] = relationship()
    positions: Mapped[List["SandboxPosition"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan"
    )
    orders: Mapped[List["SandboxOrder"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan"
    )
    transactions: Mapped[List["SandboxTransaction"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan"
    )


class SandboxPosition(Base):
    """Sandbox position holding."""

    __tablename__ = "sandbox_positions"

    id: Mapped[uuid.UUID] = get_uuid_column()
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sandbox_accounts.id", ondelete="CASCADE"),
        nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(50), default="equity")

    # Position details
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(15, 6), nullable=False)
    average_open_price: Mapped[Decimal] = mapped_column(DECIMAL(15, 4), nullable=False)
    current_price: Mapped[Decimal] = mapped_column(DECIMAL(15, 4), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), nullable=False)

    # P&L tracking
    unrealized_pnl: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal('0.00'))
    realized_pnl: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal('0.00'))

    # Options-specific fields
    option_type: Mapped[Optional[str]] = mapped_column(String(10))
    strike_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 4))
    expiration_date: Mapped[Optional[datetime]] = get_timestamp_column(nullable=True)

    # Greeks for options
    delta: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(8, 6))
    gamma: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(8, 6))
    theta: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(8, 6))
    vega: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(8, 6))

    opened_at: Mapped[datetime] = get_timestamp_column()
    updated_at: Mapped[datetime] = get_timestamp_column()

    # Relationships
    account: Mapped["SandboxAccount"] = relationship(back_populates="positions")


class SandboxOrder(Base):
    """Sandbox order execution."""

    __tablename__ = "sandbox_orders"

    id: Mapped[uuid.UUID] = get_uuid_column()
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sandbox_accounts.id", ondelete="CASCADE"),
        nullable=False
    )
    order_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    # Order details
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # buy, sell
    order_type: Mapped[str] = mapped_column(String(20), default="market")
    quantity: Mapped[Decimal] = mapped_column(DECIMAL(15, 6), nullable=False)
    price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 4))
    stop_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 4))

    # Execution details
    status: Mapped[SandboxOrderStatus] = mapped_column(
        Enum(SandboxOrderStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]),
        default=SandboxOrderStatus.PENDING,
        nullable=False
    )
    filled_quantity: Mapped[Decimal] = mapped_column(DECIMAL(15, 6), default=Decimal('0.0'))
    average_fill_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 4))

    # Simulation parameters
    simulated_slippage: Mapped[Decimal] = mapped_column(DECIMAL(8, 4), default=Decimal('0.01'))
    simulated_commission: Mapped[Decimal] = mapped_column(DECIMAL(8, 2), default=Decimal('1.00'))
    execution_delay_ms: Mapped[int] = mapped_column(Integer, default=100)

    # Time tracking
    submitted_at: Mapped[datetime] = get_timestamp_column()
    filled_at: Mapped[Optional[datetime]] = get_timestamp_column(nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = get_timestamp_column(nullable=True)

    # Relationships
    account: Mapped["SandboxAccount"] = relationship(back_populates="orders")
    transactions: Mapped[List["SandboxTransaction"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan"
    )


class SandboxTransaction(Base):
    """Sandbox transaction history."""

    __tablename__ = "sandbox_transactions"

    id: Mapped[uuid.UUID] = get_uuid_column()
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sandbox_accounts.id", ondelete="CASCADE"),
        nullable=False
    )
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("sandbox_orders.id", ondelete="SET NULL"),
        nullable=True
    )

    # Transaction details
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)  # trade, fee, dividend, interest
    symbol: Mapped[Optional[str]] = mapped_column(String(50))
    quantity: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 6))
    price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(15, 4))
    amount: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), nullable=False)

    # Running balances
    balance_before: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), nullable=False)

    # Metadata
    description: Mapped[Optional[str]] = mapped_column(Text)
    executed_at: Mapped[datetime] = get_timestamp_column()

    # Relationships
    account: Mapped["SandboxAccount"] = relationship(back_populates="transactions")
    order: Mapped[Optional["SandboxOrder"]] = relationship(back_populates="transactions")


class SandboxMarketData(Base):
    """Simulated market data for sandbox."""

    __tablename__ = "sandbox_market_data"

    id: Mapped[uuid.UUID] = get_uuid_column()
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Price data
    bid: Mapped[Decimal] = mapped_column(DECIMAL(15, 4), nullable=False)
    ask: Mapped[Decimal] = mapped_column(DECIMAL(15, 4), nullable=False)
    last: Mapped[Decimal] = mapped_column(DECIMAL(15, 4), nullable=False)
    open_price: Mapped[Decimal] = mapped_column(DECIMAL(15, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(DECIMAL(15, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(DECIMAL(15, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(DECIMAL(15, 4), nullable=False)

    # Volume and timing
    volume: Mapped[int] = mapped_column(Integer, default=0)
    bid_size: Mapped[int] = mapped_column(Integer, default=100)
    ask_size: Mapped[int] = mapped_column(Integer, default=100)

    # Simulation metadata
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    volatility: Mapped[Decimal] = mapped_column(DECIMAL(8, 4), default=Decimal('0.20'))

    updated_at: Mapped[datetime] = get_timestamp_column()


class SandboxReset(Base):
    """Sandbox reset audit trail."""

    __tablename__ = "sandbox_resets"

    id: Mapped[uuid.UUID] = get_uuid_column()
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sandbox_accounts.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    # Reset details
    reset_type: Mapped[str] = mapped_column(String(50), default="full")  # full, positions_only, balance_only
    previous_balance: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), nullable=False)
    new_balance: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), nullable=False)
    positions_cleared: Mapped[int] = mapped_column(Integer, default=0)
    orders_cancelled: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata
    reason: Mapped[Optional[str]] = mapped_column(Text)
    reset_at: Mapped[datetime] = get_timestamp_column()

    # Relationships
    account: Mapped["SandboxAccount"] = relationship()
    user: Mapped["User"] = relationship()


class SandboxConfiguration(Base):
    """Global sandbox configuration settings."""

    __tablename__ = "sandbox_configurations"

    id: Mapped[uuid.UUID] = get_uuid_column()

    # Market simulation settings
    market_hours_start: Mapped[str] = mapped_column(String(10), default="09:30")
    market_hours_end: Mapped[str] = mapped_column(String(10), default="16:00")
    enable_after_hours: Mapped[bool] = mapped_column(Boolean, default=False)

    # Execution simulation
    default_slippage_bps: Mapped[int] = mapped_column(Integer, default=1)  # basis points
    default_commission: Mapped[Decimal] = mapped_column(DECIMAL(8, 2), default=Decimal('1.00'))
    execution_delay_min_ms: Mapped[int] = mapped_column(Integer, default=50)
    execution_delay_max_ms: Mapped[int] = mapped_column(Integer, default=500)

    # Risk settings
    max_position_size: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal('1000000.00'))
    max_daily_loss: Mapped[Decimal] = mapped_column(DECIMAL(15, 2), default=Decimal('50000.00'))
    pdt_enforcement: Mapped[bool] = mapped_column(Boolean, default=True)

    # Educational features
    show_educational_tips: Mapped[bool] = mapped_column(Boolean, default=True)
    highlight_differences: Mapped[bool] = mapped_column(Boolean, default=True)
    require_confirmations: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = get_timestamp_column()
    updated_at: Mapped[datetime] = get_timestamp_column()