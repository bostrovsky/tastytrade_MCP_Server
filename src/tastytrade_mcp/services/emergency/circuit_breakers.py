"""Circuit breaker monitoring system for automatic trading halts."""
import uuid
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache import get_cache
from .models import (
    CircuitBreaker, CircuitBreakerEvent, CircuitBreakerType,
    EmergencyAlert, AlertLevel, EmergencyStatus
)


class CircuitBreakerMonitor:
    """Monitors portfolio and market conditions for automatic circuit breaker triggers."""

    def __init__(self, session: AsyncSession):
        """Initialize circuit breaker monitor."""
        self.session = session
        self.cache = get_cache()

        # Default circuit breaker thresholds
        self.default_thresholds = {
            CircuitBreakerType.PORTFOLIO_LOSS: Decimal("0.20"),  # 20% portfolio loss
            CircuitBreakerType.DAILY_LOSS_LIMIT: Decimal("0.10"),  # 10% daily loss
            CircuitBreakerType.POSITION_LOSS: Decimal("0.15"),  # 15% single position loss
            CircuitBreakerType.ACCOUNT_DRAWDOWN: Decimal("0.25"),  # 25% account drawdown
            CircuitBreakerType.CONCENTRATION_RISK: Decimal("0.40"),  # 40% in single position
            CircuitBreakerType.MARKET_VOLATILITY: Decimal("0.05")   # 5% VIX spike
        }

    async def check_circuit_breakers(
        self,
        account_number: str,
        force_check: bool = False
    ) -> List[CircuitBreakerEvent]:
        """Check all circuit breakers for an account."""
        # Check if we've already checked recently (unless forced)
        if not force_check:
            last_check = await self._get_last_check_time(account_number)
            if last_check and (datetime.utcnow() - last_check).seconds < 60:
                return []

        # Get active circuit breakers for account
        breakers = await self._get_active_circuit_breakers(account_number)

        triggered_events = []

        for breaker in breakers:
            try:
                event = await self._check_individual_breaker(breaker)
                if event:
                    triggered_events.append(event)

                    # Execute emergency actions if auto-trigger enabled
                    if breaker.auto_trigger:
                        await self._execute_circuit_breaker_actions(event)

            except Exception as e:
                print(f"Error checking circuit breaker {breaker.breaker_id}: {e}")

        # Update last check time
        await self._update_last_check_time(account_number)

        return triggered_events

    async def _check_individual_breaker(
        self,
        breaker: CircuitBreaker
    ) -> Optional[CircuitBreakerEvent]:
        """Check a specific circuit breaker."""
        # Check cooling period
        if breaker.last_triggered:
            cooling_end = breaker.last_triggered + timedelta(minutes=breaker.cooling_period_minutes)
            if datetime.utcnow() < cooling_end:
                return None

        if breaker.breaker_type == CircuitBreakerType.PORTFOLIO_LOSS:
            return await self._check_portfolio_loss(breaker)
        elif breaker.breaker_type == CircuitBreakerType.DAILY_LOSS_LIMIT:
            return await self._check_daily_loss_limit(breaker)
        elif breaker.breaker_type == CircuitBreakerType.POSITION_LOSS:
            return await self._check_position_loss(breaker)
        elif breaker.breaker_type == CircuitBreakerType.ACCOUNT_DRAWDOWN:
            return await self._check_account_drawdown(breaker)
        elif breaker.breaker_type == CircuitBreakerType.CONCENTRATION_RISK:
            return await self._check_concentration_risk(breaker)
        elif breaker.breaker_type == CircuitBreakerType.MARKET_VOLATILITY:
            return await self._check_market_volatility(breaker)

        return None

    async def _check_portfolio_loss(self, breaker: CircuitBreaker) -> Optional[CircuitBreakerEvent]:
        """Check portfolio loss circuit breaker."""
        # Get current portfolio value and P&L
        portfolio_data = await self._get_portfolio_data(breaker.account_number)

        if not portfolio_data:
            return None

        total_pnl = portfolio_data.get("total_pnl", Decimal("0"))
        account_value = portfolio_data.get("account_value", Decimal("0"))

        if account_value <= 0:
            return None

        loss_percentage = abs(total_pnl) / account_value if total_pnl < 0 else Decimal("0")

        if loss_percentage >= breaker.threshold_percentage:
            return CircuitBreakerEvent(
                event_id=str(uuid.uuid4()),
                breaker_id=breaker.breaker_id,
                account_number=breaker.account_number,
                trigger_value=loss_percentage,
                threshold_value=breaker.threshold_percentage,
                trigger_reason=f"Portfolio loss of {loss_percentage:.1%} exceeds threshold of {breaker.threshold_percentage:.1%}",
                triggered_at=datetime.utcnow(),
                auto_triggered=breaker.auto_trigger,
                actions_taken=[]
            )

        return None

    async def _check_daily_loss_limit(self, breaker: CircuitBreaker) -> Optional[CircuitBreakerEvent]:
        """Check daily loss limit circuit breaker."""
        portfolio_data = await self._get_portfolio_data(breaker.account_number)

        if not portfolio_data:
            return None

        daily_pnl = portfolio_data.get("daily_pnl", Decimal("0"))
        account_value = portfolio_data.get("account_value", Decimal("0"))

        if account_value <= 0:
            return None

        daily_loss_percentage = abs(daily_pnl) / account_value if daily_pnl < 0 else Decimal("0")

        if daily_loss_percentage >= breaker.threshold_percentage:
            return CircuitBreakerEvent(
                event_id=str(uuid.uuid4()),
                breaker_id=breaker.breaker_id,
                account_number=breaker.account_number,
                trigger_value=daily_loss_percentage,
                threshold_value=breaker.threshold_percentage,
                trigger_reason=f"Daily loss of {daily_loss_percentage:.1%} exceeds limit of {breaker.threshold_percentage:.1%}",
                triggered_at=datetime.utcnow(),
                auto_triggered=breaker.auto_trigger,
                actions_taken=[]
            )

        return None

    async def _check_position_loss(self, breaker: CircuitBreaker) -> Optional[CircuitBreakerEvent]:
        """Check individual position loss circuit breaker."""
        positions = await self._get_positions_data(breaker.account_number)

        for position in positions:
            pnl_percentage = position.get("unrealized_pnl_percent", Decimal("0"))

            if abs(pnl_percentage) >= breaker.threshold_percentage and pnl_percentage < 0:
                return CircuitBreakerEvent(
                    event_id=str(uuid.uuid4()),
                    breaker_id=breaker.breaker_id,
                    account_number=breaker.account_number,
                    trigger_value=abs(pnl_percentage),
                    threshold_value=breaker.threshold_percentage,
                    trigger_reason=f"Position {position['symbol']} loss of {abs(pnl_percentage):.1%} exceeds threshold",
                    triggered_at=datetime.utcnow(),
                    auto_triggered=breaker.auto_trigger,
                    actions_taken=[]
                )

        return None

    async def _check_concentration_risk(self, breaker: CircuitBreaker) -> Optional[CircuitBreakerEvent]:
        """Check position concentration risk circuit breaker."""
        positions = await self._get_positions_data(breaker.account_number)
        portfolio_data = await self._get_portfolio_data(breaker.account_number)

        total_value = portfolio_data.get("account_value", Decimal("0"))
        if total_value <= 0:
            return None

        for position in positions:
            position_value = abs(position.get("market_value", Decimal("0")))
            concentration = position_value / total_value

            if concentration >= breaker.threshold_percentage:
                return CircuitBreakerEvent(
                    event_id=str(uuid.uuid4()),
                    breaker_id=breaker.breaker_id,
                    account_number=breaker.account_number,
                    trigger_value=concentration,
                    threshold_value=breaker.threshold_percentage,
                    trigger_reason=f"Position {position['symbol']} concentration of {concentration:.1%} exceeds threshold",
                    triggered_at=datetime.utcnow(),
                    auto_triggered=breaker.auto_trigger,
                    actions_taken=[]
                )

        return None

    async def _check_account_drawdown(self, breaker: CircuitBreaker) -> Optional[CircuitBreakerEvent]:
        """Check account drawdown circuit breaker."""
        # Get historical high and current value
        account_high = await self._get_account_high_water_mark(breaker.account_number)
        portfolio_data = await self._get_portfolio_data(breaker.account_number)

        current_value = portfolio_data.get("account_value", Decimal("0"))

        if account_high <= 0 or current_value <= 0:
            return None

        drawdown = (account_high - current_value) / account_high

        if drawdown >= breaker.threshold_percentage:
            return CircuitBreakerEvent(
                event_id=str(uuid.uuid4()),
                breaker_id=breaker.breaker_id,
                account_number=breaker.account_number,
                trigger_value=drawdown,
                threshold_value=breaker.threshold_percentage,
                trigger_reason=f"Account drawdown of {drawdown:.1%} exceeds threshold of {breaker.threshold_percentage:.1%}",
                triggered_at=datetime.utcnow(),
                auto_triggered=breaker.auto_trigger,
                actions_taken=[]
            )

        return None

    async def _check_market_volatility(self, breaker: CircuitBreaker) -> Optional[CircuitBreakerEvent]:
        """Check market volatility circuit breaker."""
        # Get current VIX or market volatility measure
        volatility_data = await self._get_market_volatility()

        if not volatility_data:
            return None

        current_vix = volatility_data.get("vix", Decimal("20"))
        vix_change = volatility_data.get("vix_change_percent", Decimal("0"))

        if abs(vix_change) >= breaker.threshold_percentage:
            return CircuitBreakerEvent(
                event_id=str(uuid.uuid4()),
                breaker_id=breaker.breaker_id,
                account_number=breaker.account_number,
                trigger_value=abs(vix_change),
                threshold_value=breaker.threshold_percentage,
                trigger_reason=f"Market volatility spike: VIX changed {vix_change:.1%} (current: {current_vix})",
                triggered_at=datetime.utcnow(),
                auto_triggered=breaker.auto_trigger,
                actions_taken=[]
            )

        return None

    async def _execute_circuit_breaker_actions(self, event: CircuitBreakerEvent) -> None:
        """Execute automated actions when circuit breaker triggers."""
        actions_taken = []

        try:
            # Import here to avoid circular imports
            from .controller import EmergencyController

            controller = EmergencyController(self.session)

            # Cancel all pending orders
            panic_response = await controller.panic_button(
                user_id="circuit_breaker_system",
                account_number=event.account_number,
                reason=f"Circuit breaker triggered: {event.trigger_reason}"
            )

            if panic_response.success:
                actions_taken.append(f"Cancelled {panic_response.orders_cancelled} pending orders")

            # Halt trading if critical threshold
            if event.trigger_value >= Decimal("0.15"):  # 15% threshold for trading halt
                halt = await controller.halt_trading(
                    user_id="circuit_breaker_system",
                    account_number=event.account_number,
                    reason=f"Automatic halt: {event.trigger_reason}",
                    override_required=True
                )
                actions_taken.append("Trading halted - manual override required")

            # Send emergency alert
            alert = EmergencyAlert(
                alert_id=str(uuid.uuid4()),
                account_number=event.account_number,
                alert_level=AlertLevel.CRITICAL,
                alert_type="circuit_breaker_triggered",
                message=event.trigger_reason,
                current_value=event.trigger_value,
                threshold_value=event.threshold_value
            )

            await self._store_emergency_alert(alert)
            actions_taken.append("Emergency alert sent")

            # Update event with actions taken
            event.actions_taken = actions_taken

            # Store circuit breaker event
            await self._store_circuit_breaker_event(event)

        except Exception as e:
            print(f"Failed to execute circuit breaker actions: {e}")

    async def create_circuit_breaker(
        self,
        account_number: str,
        breaker_type: CircuitBreakerType,
        threshold_percentage: Decimal,
        created_by: str,
        auto_trigger: bool = True
    ) -> CircuitBreaker:
        """Create a new circuit breaker."""
        breaker = CircuitBreaker(
            breaker_id=str(uuid.uuid4()),
            breaker_type=breaker_type,
            account_number=account_number,
            threshold_value=Decimal("0"),  # Will be calculated based on percentage
            threshold_percentage=threshold_percentage,
            auto_trigger=auto_trigger,
            created_by=created_by
        )

        await self._store_circuit_breaker(breaker)
        return breaker

    async def generate_graduated_alerts(
        self,
        account_number: str
    ) -> List[EmergencyAlert]:
        """Generate graduated alert levels based on current conditions."""
        alerts = []
        portfolio_data = await self._get_portfolio_data(account_number)

        if not portfolio_data:
            return alerts

        # Calculate various risk metrics
        daily_pnl = portfolio_data.get("daily_pnl", Decimal("0"))
        total_pnl = portfolio_data.get("total_pnl", Decimal("0"))
        account_value = portfolio_data.get("account_value", Decimal("0"))

        if account_value <= 0:
            return alerts

        daily_loss_pct = abs(daily_pnl) / account_value if daily_pnl < 0 else Decimal("0")
        total_loss_pct = abs(total_pnl) / account_value if total_pnl < 0 else Decimal("0")

        # Generate alerts based on thresholds
        if daily_loss_pct >= Decimal("0.15"):  # 15% daily loss
            alerts.append(EmergencyAlert(
                alert_id=str(uuid.uuid4()),
                account_number=account_number,
                alert_level=AlertLevel.EMERGENCY,
                alert_type="extreme_daily_loss",
                message=f"Extreme daily loss: {daily_loss_pct:.1%}",
                current_value=daily_loss_pct,
                threshold_value=Decimal("0.15")
            ))
        elif daily_loss_pct >= Decimal("0.10"):  # 10% daily loss
            alerts.append(EmergencyAlert(
                alert_id=str(uuid.uuid4()),
                account_number=account_number,
                alert_level=AlertLevel.CRITICAL,
                alert_type="high_daily_loss",
                message=f"High daily loss: {daily_loss_pct:.1%}",
                current_value=daily_loss_pct,
                threshold_value=Decimal("0.10")
            ))
        elif daily_loss_pct >= Decimal("0.05"):  # 5% daily loss
            alerts.append(EmergencyAlert(
                alert_id=str(uuid.uuid4()),
                account_number=account_number,
                alert_level=AlertLevel.WARNING,
                alert_type="moderate_daily_loss",
                message=f"Moderate daily loss: {daily_loss_pct:.1%}",
                current_value=daily_loss_pct,
                threshold_value=Decimal("0.05")
            ))

        # Store alerts
        for alert in alerts:
            await self._store_emergency_alert(alert)

        return alerts

    # Helper methods
    async def _get_active_circuit_breakers(self, account_number: str) -> List[CircuitBreaker]:
        """Get active circuit breakers for an account."""
        # Mock implementation - in real system, query from database
        return [
            CircuitBreaker(
                breaker_id="daily_loss_breaker",
                breaker_type=CircuitBreakerType.DAILY_LOSS_LIMIT,
                account_number=account_number,
                threshold_value=Decimal("0"),
                threshold_percentage=Decimal("0.10"),
                auto_trigger=True,
                created_by="system"
            ),
            CircuitBreaker(
                breaker_id="portfolio_loss_breaker",
                breaker_type=CircuitBreakerType.PORTFOLIO_LOSS,
                account_number=account_number,
                threshold_value=Decimal("0"),
                threshold_percentage=Decimal("0.20"),
                auto_trigger=True,
                created_by="system"
            )
        ]

    async def _get_portfolio_data(self, account_number: str) -> Dict[str, Any]:
        """Get current portfolio data."""
        # Mock implementation - in real system, get from positions service
        return {
            "account_value": Decimal("100000.00"),
            "total_pnl": Decimal("-8000.00"),  # 8% loss
            "daily_pnl": Decimal("-12000.00"),  # 12% daily loss
            "cash_balance": Decimal("25000.00")
        }

    async def _get_positions_data(self, account_number: str) -> List[Dict[str, Any]]:
        """Get current positions data."""
        # Mock implementation
        return [
            {
                "symbol": "AAPL",
                "market_value": Decimal("50000.00"),
                "unrealized_pnl_percent": Decimal("-8.5")
            },
            {
                "symbol": "TSLA",
                "market_value": Decimal("25000.00"),
                "unrealized_pnl_percent": Decimal("-18.2")  # This would trigger position loss
            }
        ]

    async def _get_account_high_water_mark(self, account_number: str) -> Decimal:
        """Get account's historical high water mark."""
        # Mock implementation
        return Decimal("120000.00")

    async def _get_market_volatility(self) -> Dict[str, Any]:
        """Get current market volatility data."""
        # Mock implementation
        return {
            "vix": Decimal("28.5"),
            "vix_change_percent": Decimal("15.2")  # This would trigger volatility breaker
        }

    async def _get_last_check_time(self, account_number: str) -> Optional[datetime]:
        """Get last circuit breaker check time."""
        try:
            cache_key = f"circuit_breaker_check:{account_number}"
            check_time = await self.cache.get(cache_key)
            if check_time:
                return datetime.fromisoformat(check_time)
            return None
        except Exception:
            return None

    async def _update_last_check_time(self, account_number: str) -> None:
        """Update last circuit breaker check time."""
        try:
            cache_key = f"circuit_breaker_check:{account_number}"
            await self.cache.setex(cache_key, 300, datetime.utcnow().isoformat())  # 5-minute expiry
        except Exception:
            pass

    async def _store_circuit_breaker(self, breaker: CircuitBreaker) -> None:
        """Store circuit breaker configuration."""
        try:
            cache_key = f"circuit_breaker:{breaker.breaker_id}"
            await self.cache.setex(cache_key, 86400, str(breaker.__dict__))
        except Exception as e:
            print(f"Failed to store circuit breaker: {e}")

    async def _store_circuit_breaker_event(self, event: CircuitBreakerEvent) -> None:
        """Store circuit breaker event."""
        try:
            cache_key = f"circuit_breaker_event:{event.event_id}"
            await self.cache.setex(cache_key, 86400, str(event.__dict__))
        except Exception as e:
            print(f"Failed to store circuit breaker event: {e}")

    async def _store_emergency_alert(self, alert: EmergencyAlert) -> None:
        """Store emergency alert."""
        try:
            cache_key = f"emergency_alert:{alert.alert_id}"
            await self.cache.setex(cache_key, 86400, str(alert.__dict__))
        except Exception as e:
            print(f"Failed to store emergency alert: {e}")