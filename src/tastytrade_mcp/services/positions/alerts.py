"""Position alert system."""
import asyncio
from decimal import Decimal
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..cache import get_cache
from .models import PositionAlert, StopLossOrder, TakeProfitOrder


class PositionAlertManager:
    """Manages position alerts and notifications."""

    def __init__(self):
        """Initialize alert manager."""
        self.cache = get_cache()
        self.alert_thresholds = {
            "pnl_threshold": Decimal("0.10"),  # 10% P&L threshold
            "correlation_warning": 0.7,  # 70% correlation warning
            "concentration_risk": Decimal("0.25")  # 25% position concentration
        }

    async def check_position_alerts(
        self,
        positions: List[Dict[str, Any]],
        alert_types: List[str],
        pnl_threshold: float = 10.0,
        stop_loss_orders: Optional[List[StopLossOrder]] = None,
        take_profit_orders: Optional[List[TakeProfitOrder]] = None
    ) -> List[PositionAlert]:
        """Check positions for alert conditions."""
        alerts = []

        for position in positions:
            symbol = position.get("symbol", "")

            # P&L threshold alerts
            if "pnl_threshold" in alert_types:
                pnl_percent = position.get("unrealized_pnl_percent", 0)
                if abs(pnl_percent) >= pnl_threshold:
                    severity = "warning" if pnl_percent > 0 else "critical"
                    alerts.append(PositionAlert(
                        symbol=symbol,
                        alert_type="pnl_threshold",
                        message=f"Position {symbol} has {pnl_percent:.1f}% unrealized P&L",
                        severity=severity,
                        threshold_value=Decimal(str(pnl_threshold)),
                        current_value=Decimal(str(abs(pnl_percent)))
                    ))

            # Stop-loss triggered alerts
            if "stop_loss_triggered" in alert_types and stop_loss_orders:
                current_price = position.get("current_price", 0)
                for order in stop_loss_orders:
                    if order.symbol == symbol and current_price <= order.stop_price:
                        alerts.append(PositionAlert(
                            symbol=symbol,
                            alert_type="stop_loss_triggered",
                            message=f"Stop-loss triggered for {symbol} at ${current_price}",
                            severity="critical",
                            threshold_value=order.stop_price,
                            current_value=Decimal(str(current_price))
                        ))

            # Take-profit triggered alerts
            if "take_profit_triggered" in alert_types and take_profit_orders:
                current_price = position.get("current_price", 0)
                for order in take_profit_orders:
                    if order.symbol == symbol and current_price >= order.target_price:
                        alerts.append(PositionAlert(
                            symbol=symbol,
                            alert_type="take_profit_triggered",
                            message=f"Take-profit target reached for {symbol} at ${current_price}",
                            severity="warning",
                            threshold_value=order.target_price,
                            current_value=Decimal(str(current_price))
                        ))

        # Check concentration risk
        if "concentration_risk" in alert_types:
            concentration_alerts = await self._check_concentration_risk(positions)
            alerts.extend(concentration_alerts)

        # Store alerts in cache
        if alerts:
            await self._store_alerts(alerts)

        return alerts

    async def _check_concentration_risk(self, positions: List[Dict[str, Any]]) -> List[PositionAlert]:
        """Check for position concentration risks."""
        alerts = []

        if not positions:
            return alerts

        total_value = sum(abs(pos.get("market_value", 0)) for pos in positions)
        if total_value == 0:
            return alerts

        concentration_threshold = self.alert_thresholds["concentration_risk"]

        for position in positions:
            symbol = position.get("symbol", "")
            market_value = abs(position.get("market_value", 0))
            concentration = Decimal(str(market_value)) / Decimal(str(total_value))

            if concentration > concentration_threshold:
                alerts.append(PositionAlert(
                    symbol=symbol,
                    alert_type="concentration_risk",
                    message=f"High concentration in {symbol}: {concentration:.1%} of portfolio",
                    severity="warning",
                    threshold_value=concentration_threshold,
                    current_value=concentration
                ))

        return alerts

    async def _store_alerts(self, alerts: List[PositionAlert]) -> None:
        """Store alerts in cache for persistence."""
        try:
            for alert in alerts:
                cache_key = f"position_alert:{alert.symbol}:{alert.alert_type}:{alert.created_at.isoformat()}"
                alert_data = {
                    "symbol": alert.symbol,
                    "alert_type": alert.alert_type,
                    "message": alert.message,
                    "severity": alert.severity,
                    "threshold_value": str(alert.threshold_value) if alert.threshold_value else None,
                    "current_value": str(alert.current_value) if alert.current_value else None,
                    "created_at": alert.created_at.isoformat()
                }
                await self.cache.setex(cache_key, 86400, str(alert_data))  # 24-hour expiry
        except Exception as e:
            # Log error but don't fail the alert check
            print(f"Warning: Failed to cache alerts: {e}")

    async def get_recent_alerts(self, symbol: str = None, hours: int = 24) -> List[PositionAlert]:
        """Get recent alerts from cache."""
        try:
            pattern = f"position_alert:{symbol}:*" if symbol else "position_alert:*"
            keys = await self.cache.keys(pattern)

            alerts = []
            for key in keys:
                alert_data = await self.cache.get(key)
                if alert_data:
                    # Parse alert data and create PositionAlert object
                    # This is a simplified version - in practice you'd need proper JSON parsing
                    pass

            return alerts
        except Exception:
            return []

    async def clear_alerts(self, symbol: str = None) -> None:
        """Clear alerts for a symbol or all alerts."""
        try:
            pattern = f"position_alert:{symbol}:*" if symbol else "position_alert:*"
            keys = await self.cache.keys(pattern)
            if keys:
                await self.cache.delete(*keys)
        except Exception as e:
            print(f"Warning: Failed to clear alerts: {e}")

    def set_alert_threshold(self, alert_type: str, threshold: float) -> None:
        """Set custom alert threshold."""
        if alert_type in self.alert_thresholds:
            self.alert_thresholds[alert_type] = Decimal(str(threshold))

    def get_alert_thresholds(self) -> Dict[str, Any]:
        """Get current alert thresholds."""
        return dict(self.alert_thresholds)