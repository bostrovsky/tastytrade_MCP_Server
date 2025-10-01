"""Emergency control data models."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Any, Optional
from uuid import UUID


class EmergencyActionType(Enum):
    """Types of emergency actions."""
    PANIC_BUTTON = "panic_button"
    EMERGENCY_EXIT = "emergency_exit"
    CIRCUIT_BREAKER = "circuit_breaker"
    TRADING_HALT = "trading_halt"
    MANUAL_OVERRIDE = "manual_override"


class CircuitBreakerType(Enum):
    """Types of circuit breakers."""
    PORTFOLIO_LOSS = "portfolio_loss"
    POSITION_LOSS = "position_loss"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    ACCOUNT_DRAWDOWN = "account_drawdown"
    MARKET_VOLATILITY = "market_volatility"
    CONCENTRATION_RISK = "concentration_risk"


class AlertLevel(Enum):
    """Emergency alert levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class EmergencyStatus(Enum):
    """Emergency system status."""
    NORMAL = "normal"
    WARNING = "warning"
    CIRCUIT_BREAKER_TRIGGERED = "circuit_breaker_triggered"
    TRADING_HALTED = "trading_halted"
    EMERGENCY_MODE = "emergency_mode"


@dataclass
class EmergencyAction:
    """Emergency action record."""
    action_id: str
    action_type: EmergencyActionType
    user_id: str
    account_number: str
    trigger_reason: str
    executed_at: datetime
    orders_affected: int = 0
    positions_affected: int = 0
    estimated_impact: Optional[Decimal] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class EmergencyResponse:
    """Response from emergency action."""
    action_id: str
    action_type: EmergencyActionType
    success: bool
    message: str
    orders_cancelled: int = 0
    positions_closed: int = 0
    estimated_impact: Optional[Decimal] = None
    recovery_instructions: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class CircuitBreaker:
    """Circuit breaker configuration."""
    breaker_id: str
    breaker_type: CircuitBreakerType
    account_number: str
    threshold_value: Decimal
    threshold_percentage: Optional[Decimal] = None
    lookback_period_minutes: int = 1440  # 24 hours default
    enabled: bool = True
    auto_trigger: bool = True
    cooling_period_minutes: int = 60
    created_by: str = ""
    created_at: datetime = None
    last_triggered: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class CircuitBreakerEvent:
    """Circuit breaker trigger event."""
    event_id: str
    breaker_id: str
    account_number: str
    trigger_value: Decimal
    threshold_value: Decimal
    trigger_reason: str
    triggered_at: datetime
    auto_triggered: bool
    actions_taken: List[str]
    recovery_time: Optional[datetime] = None


@dataclass
class TradingHalt:
    """Trading halt status."""
    halt_id: str
    account_number: str
    reason: str
    halted_at: datetime
    halted_by: str
    auto_halt: bool
    override_required: bool = True
    resumed_at: Optional[datetime] = None
    resumed_by: Optional[str] = None


@dataclass
class EmergencyAlert:
    """Emergency system alert."""
    alert_id: str
    account_number: str
    alert_level: AlertLevel
    alert_type: str
    message: str
    current_value: Decimal
    threshold_value: Optional[Decimal] = None
    created_at: datetime = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class PortfolioSnapshot:
    """Portfolio snapshot for emergency analysis."""
    account_number: str
    snapshot_time: datetime
    total_market_value: Decimal
    cash_balance: Decimal
    total_pnl: Decimal
    daily_pnl: Decimal
    unrealized_pnl: Decimal
    position_count: int
    open_order_count: int
    concentration_risk_score: float
    max_position_exposure: Decimal


@dataclass
class EmergencyNotification:
    """Emergency notification for external systems."""
    notification_id: str
    account_number: str
    notification_type: str
    priority: AlertLevel
    message: str
    recipients: List[str]
    channels: List[str]  # email, sms, webhook, etc.
    sent_at: Optional[datetime] = None
    delivery_status: Optional[Dict[str, str]] = None


@dataclass
class RecoveryProcedure:
    """Recovery procedure after emergency action."""
    procedure_id: str
    emergency_action_id: str
    account_number: str
    procedure_type: str
    steps: List[str]
    required_approvals: List[str]
    estimated_recovery_time: int  # minutes
    status: str = "pending"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    approved_by: Optional[List[str]] = None