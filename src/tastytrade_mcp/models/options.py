"""Options trading models and enums."""
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, DateTime, Enum as SQLEnum, ForeignKey, Integer,
    JSON, Numeric, String, Text, Boolean
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from tastytrade_mcp.db.base import Base


class OptionType(str, Enum):
    """Option type enumeration."""
    CALL = "call"
    PUT = "put"


class OptionAction(str, Enum):
    """Option action enumeration."""
    BUY_TO_OPEN = "buy_to_open"
    BUY_TO_CLOSE = "buy_to_close"
    SELL_TO_OPEN = "sell_to_open"
    SELL_TO_CLOSE = "sell_to_close"


class OptionStrategy(str, Enum):
    """Common option strategy patterns."""
    SINGLE = "single"
    VERTICAL_SPREAD = "vertical_spread"
    IRON_CONDOR = "iron_condor"
    IRON_BUTTERFLY = "iron_butterfly"
    CALENDAR_SPREAD = "calendar_spread"
    DIAGONAL_SPREAD = "diagonal_spread"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    BUTTERFLY = "butterfly"
    CONDOR = "condor"
    COLLAR = "collar"
    COVERED_CALL = "covered_call"
    CASH_SECURED_PUT = "cash_secured_put"
    CUSTOM = "custom"


class OptionApprovalLevel(str, Enum):
    """Option trading approval levels."""
    LEVEL_0 = "level_0"  # No options
    LEVEL_1 = "level_1"  # Covered calls, cash-secured puts
    LEVEL_2 = "level_2"  # Long options, spreads
    LEVEL_3 = "level_3"  # Naked options


class OptionOrder(Base):
    """Options order model."""

    __tablename__ = "option_orders"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # User and account
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    account_id = Column(String(50), nullable=False)

    # Order reference
    external_order_id = Column(String(100), unique=True)
    preview_token = Column(String(128))

    # Strategy information
    strategy = Column(SQLEnum(OptionStrategy), nullable=False)
    strategy_name = Column(String(100))

    # Order status
    status = Column(String(20), nullable=False)

    # Risk metrics (stored as JSON)
    greeks = Column(JSON)  # {delta, gamma, theta, vega, rho}
    risk_metrics = Column(JSON)  # {max_loss, max_gain, breakeven_points}

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    submitted_at = Column(DateTime(timezone=True))
    filled_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))

    # Relationships
    legs = relationship("OptionLeg", back_populates="order", cascade="all, delete-orphan")


class OptionLeg(Base):
    """Individual leg of an options order."""

    __tablename__ = "option_legs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    order_id = Column(PGUUID(as_uuid=True), ForeignKey("option_orders.id"), nullable=False)

    # Option details
    underlying_symbol = Column(String(20), nullable=False)
    option_symbol = Column(String(50), nullable=False)  # OCC symbol

    # Contract specifications
    strike_price = Column(Numeric(12, 4), nullable=False)
    expiration_date = Column(DateTime, nullable=False)
    option_type = Column(SQLEnum(OptionType), nullable=False)

    # Order details
    action = Column(SQLEnum(OptionAction), nullable=False)
    quantity = Column(Integer, nullable=False)

    # Pricing
    limit_price = Column(Numeric(12, 4))
    fill_price = Column(Numeric(12, 4))

    # Greeks at order time
    delta = Column(Numeric(8, 6))
    gamma = Column(Numeric(8, 6))
    theta = Column(Numeric(8, 6))
    vega = Column(Numeric(8, 6))
    rho = Column(Numeric(8, 6))

    # Implied volatility
    implied_volatility = Column(Numeric(8, 4))

    # Status
    filled_quantity = Column(Integer, default=0)
    status = Column(String(20))

    # Relationships
    order = relationship("OptionOrder", back_populates="legs")


class OptionRiskAssessment(Base):
    """Risk assessment for options orders."""

    __tablename__ = "option_risk_assessments"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    order_id = Column(PGUUID(as_uuid=True), ForeignKey("option_orders.id"), nullable=False)

    # Risk metrics
    max_loss = Column(Numeric(12, 2))
    max_gain = Column(Numeric(12, 2))
    probability_profit = Column(Numeric(5, 4))  # 0.0000 to 1.0000
    expected_value = Column(Numeric(12, 2))

    # Assignment risk
    assignment_risk_level = Column(String(20))  # LOW, MEDIUM, HIGH
    early_assignment_risk = Column(Boolean, default=False)

    # Portfolio impact
    portfolio_delta = Column(Numeric(12, 4))
    portfolio_gamma = Column(Numeric(12, 4))
    portfolio_theta = Column(Numeric(12, 4))
    portfolio_vega = Column(Numeric(12, 4))

    # Margin requirements
    initial_margin = Column(Numeric(12, 2))
    maintenance_margin = Column(Numeric(12, 2))
    buying_power_effect = Column(Numeric(12, 2))

    # IV analysis
    iv_rank = Column(Numeric(5, 2))  # 0-100
    iv_percentile = Column(Numeric(5, 2))  # 0-100

    # Warnings (stored as JSON array)
    warnings = Column(JSON)  # [{type, message, severity}]

    # Approval check
    required_approval_level = Column(SQLEnum(OptionApprovalLevel))
    approval_passed = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OptionChainCache(Base):
    """Cache for options chain data."""

    __tablename__ = "option_chain_cache"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Symbol and expiration
    underlying_symbol = Column(String(20), nullable=False)
    expiration_date = Column(DateTime, nullable=False)

    # Chain data (stored as JSON)
    chain_data = Column(JSON)  # Full chain with strikes, Greeks, etc.

    # Cache metadata
    fetched_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Underlying price at fetch time
    underlying_price = Column(Numeric(12, 4))

