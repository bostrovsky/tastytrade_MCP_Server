"""Position management data models."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional


@dataclass
class PositionAlert:
    """Position alert data."""
    symbol: str
    alert_type: str  # pnl_threshold, stop_loss_triggered, take_profit_triggered, concentration_risk
    message: str
    severity: str  # info, warning, critical
    threshold_value: Optional[Decimal] = None
    current_value: Optional[Decimal] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class StopLossOrder:
    """Stop-loss order configuration."""
    order_id: str
    symbol: str
    stop_price: Decimal
    order_type: str  # market, limit
    limit_price: Optional[Decimal] = None
    quantity: Optional[Decimal] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class TakeProfitOrder:
    """Take-profit order configuration."""
    order_id: str
    symbol: str
    target_price: Decimal
    order_type: str  # market, limit
    quantity: Optional[Decimal] = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class PositionSizing:
    """Position sizing recommendation."""
    symbol: str
    current_position: Decimal
    recommended_position: Decimal
    risk_level: str  # LOW, MEDIUM, HIGH
    max_position_size: Decimal
    reasoning: str


@dataclass
class CorrelationAnalysis:
    """Position correlation analysis results."""
    high_correlations: List[Dict[str, Any]]
    concentration_risks: List[str]
    diversification_score: float  # 0-10 scale
    recommendations: List[str]


@dataclass
class RebalancingSuggestion:
    """Portfolio rebalancing suggestion."""
    symbol: str
    current_allocation: Decimal
    target_allocation: Decimal
    difference: Decimal
    action: str  # BUY, SELL, HOLD
    recommended_quantity: Decimal
    priority: str  # HIGH, MEDIUM, LOW


@dataclass
class BulkOperationResult:
    """Result of bulk position operation."""
    operation_type: str
    total_symbols: int
    successful_operations: List[Dict[str, Any]]
    failed_operations: List[Dict[str, Any]]
    execution_time: float


@dataclass
class PositionAnalytics:
    """Position performance analytics."""
    total_positions: int
    total_market_value: Decimal
    total_unrealized_pnl: Decimal
    total_realized_pnl: Decimal
    win_rate: float
    largest_winner: Decimal
    largest_loser: Decimal
    portfolio_beta: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None