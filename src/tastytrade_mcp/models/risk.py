"""Risk management models and enums."""
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Column, DateTime, Enum as SQLEnum, ForeignKey, Integer,
    JSON, Numeric, String, Text, Boolean, Index
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from tastytrade_mcp.db.base import Base


class RuleType(str, Enum):
    """Risk rule type enumeration."""
    POSITION_LIMIT = "position_limit"
    CONCENTRATION = "concentration"
    VAR_LIMIT = "var_limit"
    BUYING_POWER = "buying_power"
    DAILY_LOSS = "daily_loss"
    PDT_CHECK = "pdt_check"  # Pattern Day Trader
    PORTFOLIO_BETA = "portfolio_beta"
    SECTOR_CONCENTRATION = "sector_concentration"
    MARGIN_REQUIREMENT = "margin_requirement"
    OPTIONS_APPROVAL = "options_approval"


class RuleSeverity(str, Enum):
    """Rule violation severity levels."""
    INFO = "info"
    WARNING = "warning"
    BLOCK = "block"
    ALERT = "alert"
    CRITICAL = "critical"


class OverrideType(str, Enum):
    """Risk override type enumeration."""
    MANUAL = "manual"
    EMERGENCY = "emergency"
    SYSTEM = "system"
    ADMIN = "admin"


class ValidationStatus(str, Enum):
    """Risk validation status."""
    APPROVED = "approved"
    REJECTED = "rejected"
    WARNING = "warning"
    PENDING_OVERRIDE = "pending_override"
    OVERRIDDEN = "overridden"


class RiskRule(Base):
    """Risk rule configuration model."""

    __tablename__ = "risk_rules"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Account association (null = global rule)
    account_number = Column(String(50), nullable=True)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Rule definition
    rule_type = Column(SQLEnum(RuleType), nullable=False, index=True)
    rule_name = Column(String(100), nullable=False)
    description = Column(Text)

    # Rule parameters (stored as JSON)
    parameters = Column(JSON, nullable=False)
    # Example parameters:
    # {
    #   "max_position_size": 1000,
    #   "max_position_value": 50000,
    #   "max_concentration_pct": 10
    # }

    # Rule settings
    severity = Column(SQLEnum(RuleSeverity), nullable=False, default=RuleSeverity.WARNING)
    enabled = Column(Boolean, default=True, nullable=False)
    priority = Column(Integer, default=100)  # Lower number = higher priority

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Indexes for efficient lookups
    __table_args__ = (
        Index('idx_risk_rules_account_enabled', 'account_number', 'enabled'),
        Index('idx_risk_rules_user_enabled', 'user_id', 'enabled'),
    )


class RiskValidation(Base):
    """Risk validation audit log."""

    __tablename__ = "risk_validations"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # Trade details
    account_number = Column(String(50), nullable=False)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    order_id = Column(PGUUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)

    # Trade request (full details)
    trade_request = Column(JSON, nullable=False)

    # Validation results
    validation_result = Column(JSON, nullable=False)
    status = Column(SQLEnum(ValidationStatus), nullable=False, index=True)
    approved = Column(Boolean, nullable=False)

    # Violations and warnings
    violations = Column(JSON)  # List of rule violations
    warnings = Column(JSON)  # List of warnings

    # Portfolio impact metrics
    portfolio_impact = Column(JSON)
    # {
    #   "new_var": 5000,
    #   "new_beta": 1.2,
    #   "concentration_change": 0.05,
    #   "buying_power_impact": -10000
    # }

    # Performance metrics
    validation_time_ms = Column(Integer)

    # Timestamps
    validated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    overrides = relationship("RiskOverride", back_populates="validation", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_risk_validations_account_date', 'account_number', 'validated_at'),
        Index('idx_risk_validations_status', 'status'),
    )


class RiskOverride(Base):
    """Risk override record."""

    __tablename__ = "risk_overrides"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    validation_id = Column(PGUUID(as_uuid=True), ForeignKey("risk_validations.id"), nullable=False)

    # Override details
    override_type = Column(SQLEnum(OverrideType), nullable=False)
    override_reason = Column(Text, nullable=False)

    # Approval
    approved_by = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Expiration (for temporary overrides)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Additional conditions or notes
    conditions = Column(JSON)  # Any conditions attached to the override

    # Relationships
    validation = relationship("RiskValidation", back_populates="overrides")


class AccountRiskLimits(Base):
    """Account-specific risk limits."""

    __tablename__ = "account_risk_limits"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    account_number = Column(String(50), unique=True, nullable=False)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Position limits
    max_position_size = Column(Integer, default=1000)
    max_position_value = Column(Numeric(12, 2), default=50000)
    max_portfolio_concentration = Column(Numeric(5, 4), default=0.10)  # 10%

    # Portfolio risk limits
    max_daily_var = Column(Numeric(12, 2), default=5000)
    max_portfolio_beta = Column(Numeric(6, 3), default=1.5)
    max_sector_concentration = Column(Numeric(5, 4), default=0.25)  # 25%

    # Account limits
    min_buying_power_buffer = Column(Numeric(12, 2), default=1000)
    max_daily_loss = Column(Numeric(12, 2), default=10000)
    max_daily_trades = Column(Integer, default=100)

    # Pattern Day Trader settings
    is_pdt = Column(Boolean, default=False)
    pdt_min_equity = Column(Numeric(12, 2), default=25000)

    # Options trading level
    options_approval_level = Column(Integer, default=0)  # 0-4

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DailyRiskMetrics(Base):
    """Daily risk metrics tracking."""

    __tablename__ = "daily_risk_metrics"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    account_number = Column(String(50), nullable=False)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    date = Column(DateTime, nullable=False, index=True)

    # Daily P&L tracking
    realized_pnl = Column(Numeric(12, 2), default=0)
    unrealized_pnl = Column(Numeric(12, 2), default=0)
    total_pnl = Column(Numeric(12, 2), default=0)

    # Trade counts
    trades_executed = Column(Integer, default=0)
    trades_blocked = Column(Integer, default=0)
    trades_overridden = Column(Integer, default=0)

    # Risk metrics
    current_var = Column(Numeric(12, 2))
    current_beta = Column(Numeric(6, 3))
    max_drawdown = Column(Numeric(12, 2))

    # Position metrics
    position_count = Column(Integer, default=0)
    max_concentration = Column(Numeric(5, 4))  # Highest single position concentration

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Unique constraint on account_number and date
    __table_args__ = (
        Index('idx_daily_risk_metrics_account_date', 'account_number', 'date', unique=True),
    )