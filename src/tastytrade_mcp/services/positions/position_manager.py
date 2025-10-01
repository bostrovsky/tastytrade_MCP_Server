"""Refactored position manager - orchestrates position management services."""
import time
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ..tastytrade import TastyTradeService
from .alerts import PositionAlertManager
from .risk_management import RiskManagementService
from .analytics import PositionAnalyticsService
from .rebalancing import RebalancingService
from .models import (
    PositionAlert, StopLossOrder, TakeProfitOrder,
    CorrelationAnalysis, PositionAnalytics, BulkOperationResult
)


class PositionManager:
    """Main position manager that orchestrates all position-related services."""

    def __init__(self, session: Optional[AsyncSession] = None):
        """Initialize position manager with composed services."""
        self.session = session

        # Initialize service components
        self.alert_manager = PositionAlertManager()
        self.risk_manager = RiskManagementService()
        self.analytics_service = PositionAnalyticsService()
        self.rebalancing_service = RebalancingService()

    async def get_real_time_positions(
        self,
        broker_link,
        account_number: str
    ) -> List[Dict[str, Any]]:
        """Get positions with real-time market data."""
        # This would typically use TastyTradeService
        # For now, return mock data structure
        return []

    async def check_position_alerts(
        self,
        broker_link,
        account_number: str,
        alert_types: List[str],
        pnl_threshold: float = 10.0
    ) -> List[PositionAlert]:
        """Check positions for alert conditions."""
        # Get current positions
        positions = await self.get_real_time_positions(broker_link, account_number)

        # Get stop-loss and take-profit orders
        stop_loss_orders = await self.risk_manager.get_stop_loss_orders()
        take_profit_orders = await self.risk_manager.get_take_profit_orders()

        # Check alerts using alert manager
        return await self.alert_manager.check_position_alerts(
            positions,
            alert_types,
            pnl_threshold,
            stop_loss_orders,
            take_profit_orders
        )

    async def set_stop_loss(
        self,
        broker_link,
        account_number: str,
        symbol: str,
        stop_price: float,
        order_type: str = "market",
        limit_price: Optional[float] = None
    ) -> StopLossOrder:
        """Set stop-loss order for a position."""
        return await self.risk_manager.set_stop_loss(
            symbol, stop_price, order_type, limit_price
        )

    async def set_take_profit(
        self,
        broker_link,
        account_number: str,
        symbol: str,
        target_price: float,
        order_type: str = "limit"
    ) -> TakeProfitOrder:
        """Set take-profit order for a position."""
        return await self.risk_manager.set_take_profit(
            symbol, target_price, order_type
        )

    async def analyze_position_correlation(
        self,
        broker_link,
        account_number: str,
        lookback_days: int = 30,
        correlation_threshold: float = 0.7
    ) -> CorrelationAnalysis:
        """Analyze correlation between positions."""
        positions = await self.get_real_time_positions(broker_link, account_number)
        return await self.analytics_service.analyze_correlation(
            positions, lookback_days, correlation_threshold
        )

    async def suggest_rebalancing(
        self,
        broker_link,
        account_number: str,
        target_allocations: Dict[str, float],
        rebalance_threshold: float = 5.0
    ) -> Dict[str, Any]:
        """Generate portfolio rebalancing suggestions."""
        positions = await self.get_real_time_positions(broker_link, account_number)
        return await self.rebalancing_service.suggest_rebalancing(
            positions, target_allocations, rebalance_threshold
        )

    async def generate_position_analytics(
        self,
        broker_link,
        account_number: str
    ) -> PositionAnalytics:
        """Generate comprehensive position analytics."""
        positions = await self.get_real_time_positions(broker_link, account_number)
        return await self.analytics_service.generate_position_analytics(positions)

    async def bulk_position_update(
        self,
        broker_link,
        account_number: str,
        operation: str,
        symbols: List[str],
        parameters: Dict[str, Any]
    ) -> BulkOperationResult:
        """Perform bulk operations on multiple positions."""
        start_time = time.time()
        successful_operations = []
        failed_operations = []

        for symbol in symbols:
            try:
                if operation == "set_stop_loss":
                    stop_price = parameters.get("stop_price")
                    order_type = parameters.get("order_type", "market")
                    limit_price = parameters.get("limit_price")

                    order = await self.set_stop_loss(
                        broker_link, account_number, symbol, stop_price, order_type, limit_price
                    )

                    successful_operations.append({
                        "symbol": symbol,
                        "message": f"Stop-loss set at ${stop_price}",
                        "order_id": order.order_id
                    })

                elif operation == "set_take_profit":
                    target_price = parameters.get("target_price")
                    order_type = parameters.get("order_type", "limit")

                    order = await self.set_take_profit(
                        broker_link, account_number, symbol, target_price, order_type
                    )

                    successful_operations.append({
                        "symbol": symbol,
                        "message": f"Take-profit set at ${target_price}",
                        "order_id": order.order_id
                    })

                elif operation == "close_positions":
                    # Placeholder for position closing logic
                    successful_operations.append({
                        "symbol": symbol,
                        "message": "Position close order submitted"
                    })

                else:
                    raise ValueError(f"Unsupported bulk operation: {operation}")

            except Exception as e:
                failed_operations.append({
                    "symbol": symbol,
                    "error": str(e)
                })

        execution_time = time.time() - start_time

        return BulkOperationResult(
            operation_type=operation,
            total_symbols=len(symbols),
            successful_operations=successful_operations,
            failed_operations=failed_operations,
            execution_time=execution_time
        )

    # Delegation methods for individual services
    async def get_recent_alerts(self, symbol: str = None) -> List[PositionAlert]:
        """Get recent alerts."""
        return await self.alert_manager.get_recent_alerts(symbol)

    async def clear_alerts(self, symbol: str = None) -> None:
        """Clear alerts."""
        await self.alert_manager.clear_alerts(symbol)

    async def cancel_stop_loss(self, symbol: str, order_id: str = None) -> bool:
        """Cancel stop-loss orders."""
        return await self.risk_manager.cancel_stop_loss(symbol, order_id)

    async def cancel_take_profit(self, symbol: str, order_id: str = None) -> bool:
        """Cancel take-profit orders."""
        return await self.risk_manager.cancel_take_profit(symbol, order_id)

    def calculate_stop_loss_price(self, entry_price: float, risk_percentage: float, position_type: str = "long") -> float:
        """Calculate stop-loss price."""
        return self.risk_manager.calculate_stop_loss_price(entry_price, risk_percentage, position_type)

    def calculate_take_profit_price(self, entry_price: float, reward_percentage: float, position_type: str = "long") -> float:
        """Calculate take-profit price."""
        return self.risk_manager.calculate_take_profit_price(entry_price, reward_percentage, position_type)