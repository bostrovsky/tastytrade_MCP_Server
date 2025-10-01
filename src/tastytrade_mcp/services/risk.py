"""Risk validation service for pre-trade checks."""
import asyncio
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
import time

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from tastytrade_mcp.models.risk import (
    RiskRule, RiskValidation, RiskOverride, AccountRiskLimits,
    DailyRiskMetrics, RuleType, RuleSeverity, ValidationStatus
)
from tastytrade_mcp.models.user import User
from tastytrade_mcp.models.order import Order, OrderSide, OrderType
from tastytrade_mcp.services.tastytrade import TastyTradeService
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class RiskViolation:
    """Represents a risk rule violation."""

    def __init__(
        self,
        rule_type: RuleType,
        rule_name: str,
        severity: RuleSeverity,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.rule_type = rule_type
        self.rule_name = rule_name
        self.severity = severity
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "rule_type": self.rule_type.value,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }


class RiskValidationResult:
    """Risk validation result container."""

    def __init__(self):
        self.approved = True
        self.status = ValidationStatus.APPROVED
        self.violations: List[RiskViolation] = []
        self.warnings: List[RiskViolation] = []
        self.portfolio_impact: Dict[str, Any] = {}
        self.validation_time_ms = 0

    def add_violation(self, violation: RiskViolation):
        """Add a violation to the result."""
        if violation.severity in [RuleSeverity.BLOCK, RuleSeverity.CRITICAL]:
            self.violations.append(violation)
            self.approved = False
            self.status = ValidationStatus.REJECTED
        else:
            self.warnings.append(violation)
            if self.status == ValidationStatus.APPROVED:
                self.status = ValidationStatus.WARNING

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "approved": self.approved,
            "status": self.status.value,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": [w.to_dict() for w in self.warnings],
            "portfolio_impact": self.portfolio_impact,
            "validation_time_ms": self.validation_time_ms
        }


class RiskValidator:
    """Pre-trade risk validation service."""

    def __init__(self, session: AsyncSession, tastytrade: Optional[TastyTradeService] = None):
        self.session = session
        self.tastytrade = tastytrade

    async def validate_trade(
        self,
        trade_request: Dict[str, Any],
        account_number: str,
        user_id: UUID
    ) -> RiskValidationResult:
        """
        Validate a trade request against risk rules.

        Args:
            trade_request: Trade details (symbol, quantity, side, etc.)
            account_number: Account number string
            user_id: User UUID

        Returns:
            RiskValidationResult with approval status and any violations
        """
        start_time = time.time()
        result = RiskValidationResult()

        try:
            # Get account risk limits
            limits = await self.get_account_limits(account_number)

            # Get active risk rules
            rules = await self.get_active_rules(account_number, user_id)

            # Run validation checks in parallel
            checks = await asyncio.gather(
                self.check_position_limits(trade_request, account_number, limits),
                self.check_concentration_risk(trade_request, account_number, limits),
                self.check_buying_power(trade_request, account_number, limits),
                self.check_daily_loss_limits(account_number, limits),
                self.check_pdt_rules(trade_request, account_number, limits),
                return_exceptions=True
            )

            # Process check results
            for check in checks:
                if isinstance(check, Exception):
                    logger.error(f"Risk check failed: {check}")
                    result.add_violation(RiskViolation(
                        RuleType.POSITION_LIMIT,
                        "System Error",
                        RuleSeverity.WARNING,
                        f"Risk check failed: {str(check)}"
                    ))
                elif check:
                    result.add_violation(check)

            # Calculate portfolio impact
            result.portfolio_impact = await self.calculate_portfolio_impact(
                trade_request, account_number
            )

            # Apply custom rules
            for rule in rules:
                violation = await self.apply_custom_rule(rule, trade_request, account_number)
                if violation:
                    result.add_violation(violation)

        except Exception as e:
            logger.error(f"Risk validation error: {e}", exc_info=True)
            result.add_violation(RiskViolation(
                RuleType.POSITION_LIMIT,
                "System Error",
                RuleSeverity.CRITICAL,
                f"Risk validation system error: {str(e)}"
            ))

        # Record validation time
        result.validation_time_ms = int((time.time() - start_time) * 1000)

        # Save validation result
        await self.save_validation_result(
            trade_request, account_number, user_id, result
        )

        return result

    async def get_account_limits(self, account_number: str) -> AccountRiskLimits:
        """Get account risk limits or create defaults."""
        result = await self.session.execute(
            select(AccountRiskLimits).where(AccountRiskLimits.account_number == account_number)
        )
        limits = result.scalar_one_or_none()

        if not limits:
            # Create default limits
            limits = AccountRiskLimits(account_number=account_number)
            self.session.add(limits)
            await self.session.commit()

        return limits

    async def get_active_rules(self, account_number: str, user_id: UUID) -> List[RiskRule]:
        """Get active risk rules for an account."""
        result = await self.session.execute(
            select(RiskRule)
            .where(
                and_(
                    RiskRule.enabled == True,
                    or_(
                        RiskRule.account_number == account_number,
                        RiskRule.user_id == user_id,
                        and_(RiskRule.account_number.is_(None), RiskRule.user_id.is_(None))  # Global rules
                    )
                )
            )
            .order_by(RiskRule.priority)
        )
        return result.scalars().all()

    async def check_position_limits(
        self,
        trade_request: Dict[str, Any],
        account_number: str,
        limits: AccountRiskLimits
    ) -> Optional[RiskViolation]:
        """Check position size limits."""
        symbol = trade_request.get('symbol')
        quantity = trade_request.get('quantity', 0)
        price = trade_request.get('price')

        # Check quantity limit
        if quantity > limits.max_position_size:
            return RiskViolation(
                RuleType.POSITION_LIMIT,
                "Max Position Size",
                RuleSeverity.BLOCK,
                f"Order quantity {quantity} exceeds max position size {limits.max_position_size}",
                {"requested": quantity, "limit": limits.max_position_size}
            )

        # Check value limit if price available
        if price:
            position_value = Decimal(str(quantity)) * Decimal(str(price))
            if position_value > limits.max_position_value:
                return RiskViolation(
                    RuleType.POSITION_LIMIT,
                    "Max Position Value",
                    RuleSeverity.BLOCK,
                    f"Position value ${position_value:.2f} exceeds max ${limits.max_position_value}",
                    {"requested_value": float(position_value), "limit": float(limits.max_position_value)}
                )

        return None

    async def check_concentration_risk(
        self,
        trade_request: Dict[str, Any],
        account_number: str,
        limits: AccountRiskLimits
    ) -> Optional[RiskViolation]:
        """Check portfolio concentration risk."""
        symbol = trade_request.get('symbol')
        quantity = trade_request.get('quantity', 0)
        price = trade_request.get('price')

        if not price:
            return None  # Can't calculate concentration without price

        # Get account value from broker API
        try:
            from tastytrade_mcp.api.helpers import get_active_broker_link
            broker_link = await get_active_broker_link(self.session, None)  # TODO: Pass user
            if broker_link:
                tastytrade = TastyTradeService(self.session)
                balance_data = await tastytrade.get_balances(broker_link, account_number)
                account_value = Decimal(str(balance_data.get('net-liquidating-value', 100000)))
            else:
                logger.warning(f"No broker link found, using default account value for risk check")
                account_value = Decimal('100000')
        except Exception as e:
            logger.error(f"Failed to fetch account value: {e}")
            account_value = Decimal('100000')  # Fallback value

        position_value = Decimal(str(quantity)) * Decimal(str(price))
        concentration = position_value / account_value

        if concentration > limits.max_portfolio_concentration:
            return RiskViolation(
                RuleType.CONCENTRATION,
                "Portfolio Concentration",
                RuleSeverity.BLOCK,
                f"Position would represent {concentration:.1%} of portfolio, exceeds {limits.max_portfolio_concentration:.1%} limit",
                {
                    "concentration": float(concentration),
                    "limit": float(limits.max_portfolio_concentration)
                }
            )

        return None

    async def check_buying_power(
        self,
        trade_request: Dict[str, Any],
        account_number: str,
        limits: AccountRiskLimits
    ) -> Optional[RiskViolation]:
        """Check if account has sufficient buying power."""
        quantity = trade_request.get('quantity', 0)
        price = trade_request.get('price')
        side = trade_request.get('side', '').lower()

        if side != 'buy' or not price:
            return None  # Only check buying power for buy orders with price

        # Calculate required buying power
        required_buying_power = Decimal(str(quantity)) * Decimal(str(price))

        # Get current buying power from broker API
        try:
            from tastytrade_mcp.api.helpers import get_active_broker_link
            broker_link = await get_active_broker_link(self.session, None)  # TODO: Pass user
            if broker_link:
                tastytrade = TastyTradeService(self.session)
                balance_data = await tastytrade.get_balances(broker_link, account_number)
                # Use appropriate buying power based on account type
                if balance_data.get('stock-buying-power'):
                    current_buying_power = Decimal(str(balance_data['stock-buying-power']))
                else:
                    current_buying_power = Decimal(str(balance_data.get('cash-available-for-trading', 50000)))
            else:
                logger.warning(f"No broker link found, using default buying power for risk check")
                current_buying_power = Decimal('50000')
        except Exception as e:
            logger.error(f"Failed to fetch buying power: {e}")
            current_buying_power = Decimal('50000')  # Fallback value

        remaining = current_buying_power - required_buying_power

        if remaining < limits.min_buying_power_buffer:
            return RiskViolation(
                RuleType.BUYING_POWER,
                "Insufficient Buying Power",
                RuleSeverity.BLOCK,
                f"Trade would leave only ${remaining:.2f} buying power, minimum buffer is ${limits.min_buying_power_buffer}",
                {
                    "required": float(required_buying_power),
                    "available": float(current_buying_power),
                    "remaining_after": float(remaining),
                    "min_buffer": float(limits.min_buying_power_buffer)
                }
            )

        return None

    async def check_daily_loss_limits(
        self,
        account_number: str,
        limits: AccountRiskLimits
    ) -> Optional[RiskViolation]:
        """Check if daily loss limits have been exceeded."""
        # Get today's metrics
        today = date.today()
        result = await self.session.execute(
            select(DailyRiskMetrics)
            .where(
                and_(
                    DailyRiskMetrics.account_number == account_number,
                    func.date(DailyRiskMetrics.date) == today
                )
            )
        )
        metrics = result.scalar_one_or_none()

        if metrics and metrics.total_pnl < -limits.max_daily_loss:
            return RiskViolation(
                RuleType.DAILY_LOSS,
                "Daily Loss Limit",
                RuleSeverity.BLOCK,
                f"Daily loss ${-metrics.total_pnl:.2f} exceeds limit ${limits.max_daily_loss}",
                {
                    "current_loss": float(-metrics.total_pnl),
                    "limit": float(limits.max_daily_loss)
                }
            )

        return None

    async def check_pdt_rules(
        self,
        trade_request: Dict[str, Any],
        account_number: str,
        limits: AccountRiskLimits
    ) -> Optional[RiskViolation]:
        """Check Pattern Day Trader rules."""
        if not limits.is_pdt:
            return None

        # Check minimum equity requirement from broker API
        try:
            from tastytrade_mcp.api.helpers import get_active_broker_link
            broker_link = await get_active_broker_link(self.session, None)  # TODO: Pass user
            if broker_link:
                tastytrade = TastyTradeService(self.session)
                balance_data = await tastytrade.get_balances(broker_link, account_number)
                account_equity = Decimal(str(balance_data.get('equity-value', 30000)))
            else:
                logger.warning(f"No broker link found, using default equity for PDT check")
                account_equity = Decimal('30000')
        except Exception as e:
            logger.error(f"Failed to fetch account equity: {e}")
            account_equity = Decimal('30000')  # Fallback value

        if account_equity < limits.pdt_min_equity:
            return RiskViolation(
                RuleType.PDT_CHECK,
                "PDT Minimum Equity",
                RuleSeverity.BLOCK,
                f"Account equity ${account_equity:.2f} below PDT minimum ${limits.pdt_min_equity}",
                {
                    "current_equity": float(account_equity),
                    "required": float(limits.pdt_min_equity)
                }
            )

        # Check day trade count (would need to track actual day trades)
        # For now, just return None
        return None

    async def calculate_portfolio_impact(
        self,
        trade_request: Dict[str, Any],
        account_number: str
    ) -> Dict[str, Any]:
        """Calculate the impact of the trade on portfolio metrics."""
        # Basic portfolio impact calculations
        quantity = trade_request.get('quantity', 0)
        price = trade_request.get('price', 0)
        side = trade_request.get('side', '').lower()

        trade_value = Decimal(str(quantity)) * Decimal(str(price))

        # Calculate buying power impact
        buying_power_impact = float(trade_value) if side == 'buy' else -float(trade_value)

        # Basic concentration calculation
        try:
            from tastytrade_mcp.api.helpers import get_active_broker_link
            broker_link = await get_active_broker_link(self.session, None)
            if broker_link:
                tastytrade = TastyTradeService(self.session)
                balance_data = await tastytrade.get_balances(broker_link, account_number)
                account_value = Decimal(str(balance_data.get('net-liquidating-value', 100000)))
                concentration_change = float(trade_value / account_value) if account_value > 0 else 0
            else:
                concentration_change = 0
        except Exception:
            concentration_change = 0

        return {
            "estimated_var_change": 0,  # Would require full position data and volatility models
            "estimated_beta_change": 0,  # Would require market correlation analysis
            "concentration_change": concentration_change,
            "buying_power_impact": buying_power_impact
        }

    async def apply_custom_rule(
        self,
        rule: RiskRule,
        trade_request: Dict[str, Any],
        account_number: str
    ) -> Optional[RiskViolation]:
        """Apply a custom risk rule."""
        # Implement custom rule logic based on rule.rule_type and rule.parameters
        # This is a placeholder for custom rule evaluation
        return None

    async def save_validation_result(
        self,
        trade_request: Dict[str, Any],
        account_number: str,
        user_id: UUID,
        result: RiskValidationResult
    ) -> RiskValidation:
        """Save validation result to database."""
        validation = RiskValidation(
            account_number=account_number,
            user_id=user_id,
            trade_request=trade_request,
            validation_result=result.to_dict(),
            status=result.status,
            approved=result.approved,
            violations=[v.to_dict() for v in result.violations],
            warnings=[w.to_dict() for w in result.warnings],
            portfolio_impact=result.portfolio_impact,
            validation_time_ms=result.validation_time_ms
        )

        self.session.add(validation)
        # Don't commit here - let the calling service manage the transaction
        # await self.session.commit()

        return validation

    async def create_override(
        self,
        validation_id: UUID,
        override_type: str,
        reason: str,
        approved_by: UUID,
        expires_at: Optional[datetime] = None
    ) -> RiskOverride:
        """Create a risk override for a validation."""
        from tastytrade_mcp.models.risk import OverrideType

        override = RiskOverride(
            validation_id=validation_id,
            override_type=OverrideType[override_type.upper()],
            override_reason=reason,
            approved_by=approved_by,
            expires_at=expires_at
        )

        self.session.add(override)
        await self.session.commit()

        # Update validation status
        result = await self.session.execute(
            select(RiskValidation).where(RiskValidation.id == validation_id)
        )
        validation = result.scalar_one()
        validation.status = ValidationStatus.OVERRIDDEN
        await self.session.commit()

        return override

    async def update_daily_metrics(
        self,
        account_number: str,
        trade_executed: bool = False,
        trade_blocked: bool = False,
        pnl_update: Optional[Decimal] = None
    ):
        """Update daily risk metrics."""
        today = date.today()

        # Get or create today's metrics
        result = await self.session.execute(
            select(DailyRiskMetrics)
            .where(
                and_(
                    DailyRiskMetrics.account_number == account_number,
                    func.date(DailyRiskMetrics.date) == today
                )
            )
        )
        metrics = result.scalar_one_or_none()

        if not metrics:
            metrics = DailyRiskMetrics(
                account_number=account_number,
                date=datetime.now()
            )
            self.session.add(metrics)

        # Update counters
        if trade_executed:
            metrics.trades_executed += 1
        if trade_blocked:
            metrics.trades_blocked += 1
        if pnl_update:
            metrics.realized_pnl += pnl_update
            metrics.total_pnl = metrics.realized_pnl + metrics.unrealized_pnl

        await self.session.commit()


class RiskMonitor:
    """Real-time risk monitoring service."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_account_risk_status(self, account_number: str) -> Dict[str, Any]:
        """Get current risk status for an account."""
        # Get risk limits
        limits_result = await self.session.execute(
            select(AccountRiskLimits).where(AccountRiskLimits.account_number == account_number)
        )
        limits = limits_result.scalar_one_or_none()

        # Get today's metrics
        today = date.today()
        metrics_result = await self.session.execute(
            select(DailyRiskMetrics)
            .where(
                and_(
                    DailyRiskMetrics.account_number == account_number,
                    func.date(DailyRiskMetrics.date) == today
                )
            )
        )
        metrics = metrics_result.scalar_one_or_none()

        # Get recent validations
        validations_result = await self.session.execute(
            select(RiskValidation)
            .where(
                and_(
                    RiskValidation.account_number == account_number,
                    RiskValidation.validated_at >= datetime.utcnow() - timedelta(hours=24)
                )
            )
            .order_by(RiskValidation.validated_at.desc())
            .limit(10)
        )
        recent_validations = validations_result.scalars().all()

        return {
            "limits": limits,
            "daily_metrics": metrics,
            "recent_validations": recent_validations,
            "risk_score": self._calculate_risk_score(limits, metrics)
        }

    def _calculate_risk_score(
        self,
        limits: Optional[AccountRiskLimits],
        metrics: Optional[DailyRiskMetrics]
    ) -> float:
        """Calculate overall risk score (0-100)."""
        if not metrics:
            return 0

        score = 0

        # Factor in daily P&L
        if limits and metrics.total_pnl < 0:
            loss_ratio = abs(metrics.total_pnl) / limits.max_daily_loss
            score += min(loss_ratio * 50, 50)  # Max 50 points for losses

        # Factor in trades blocked
        if metrics.trades_executed > 0:
            block_ratio = metrics.trades_blocked / (metrics.trades_executed + metrics.trades_blocked)
            score += block_ratio * 30  # Max 30 points for blocked trades

        # Factor in concentration
        if metrics.max_concentration:
            score += float(metrics.max_concentration) * 20  # Max 20 points for concentration

        return min(score, 100)