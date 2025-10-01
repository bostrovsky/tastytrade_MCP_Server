"""Emergency control system for immediate trading halts and panic responses."""
import uuid
import asyncio
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache import get_cache
from .models import (
    EmergencyAction, EmergencyResponse, EmergencyActionType,
    TradingHalt, PortfolioSnapshot, EmergencyNotification, AlertLevel
)


class EmergencyController:
    """Handles immediate emergency responses like panic button and emergency exits."""

    def __init__(self, session: AsyncSession):
        """Initialize emergency controller."""
        self.session = session
        self.cache = get_cache()

    async def panic_button(
        self,
        user_id: str,
        account_number: str,
        reason: str = "User initiated panic button"
    ) -> EmergencyResponse:
        """Execute panic button - immediately cancel all pending orders."""
        action_id = str(uuid.uuid4())

        try:
            # Log the emergency action immediately
            emergency_action = EmergencyAction(
                action_id=action_id,
                action_type=EmergencyActionType.PANIC_BUTTON,
                user_id=user_id,
                account_number=account_number,
                trigger_reason=reason,
                executed_at=datetime.utcnow()
            )

            # Get all pending orders for the account
            pending_orders = await self._get_pending_orders(account_number)

            cancelled_orders = 0
            errors = []

            # Cancel all pending orders in parallel
            if pending_orders:
                cancel_tasks = [
                    self._cancel_order(order["order_id"])
                    for order in pending_orders
                ]

                results = await asyncio.gather(*cancel_tasks, return_exceptions=True)

                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        errors.append(f"Failed to cancel order {pending_orders[i]['order_id']}: {str(result)}")
                    else:
                        cancelled_orders += 1

            # Update emergency action
            emergency_action.orders_affected = cancelled_orders
            emergency_action.success = len(errors) == 0

            # Store in cache and database
            await self._store_emergency_action(emergency_action)

            # Send emergency notification
            await self._send_emergency_notification(
                account_number=account_number,
                notification_type="panic_button_executed",
                message=f"Panic button executed. {cancelled_orders} orders cancelled.",
                priority=AlertLevel.EMERGENCY
            )

            return EmergencyResponse(
                action_id=action_id,
                action_type=EmergencyActionType.PANIC_BUTTON,
                success=len(errors) == 0,
                message=f"Panic button executed. Cancelled {cancelled_orders} orders." +
                       (f" Errors: {'; '.join(errors)}" if errors else ""),
                orders_cancelled=cancelled_orders,
                recovery_instructions="Review cancelled orders and resubmit if needed."
            )

        except Exception as e:
            # Log failed emergency action
            emergency_action = EmergencyAction(
                action_id=action_id,
                action_type=EmergencyActionType.PANIC_BUTTON,
                user_id=user_id,
                account_number=account_number,
                trigger_reason=reason,
                executed_at=datetime.utcnow(),
                success=False,
                error_message=str(e)
            )
            await self._store_emergency_action(emergency_action)

            return EmergencyResponse(
                action_id=action_id,
                action_type=EmergencyActionType.PANIC_BUTTON,
                success=False,
                message=f"Panic button failed: {str(e)}",
                recovery_instructions="Contact support immediately."
            )

    async def emergency_exit_all_positions(
        self,
        user_id: str,
        account_number: str,
        reason: str = "Emergency position exit"
    ) -> EmergencyResponse:
        """Emergency exit all positions at market prices."""
        action_id = str(uuid.uuid4())

        try:
            # Create portfolio snapshot before exit
            snapshot = await self._create_portfolio_snapshot(account_number)

            emergency_action = EmergencyAction(
                action_id=action_id,
                action_type=EmergencyActionType.EMERGENCY_EXIT,
                user_id=user_id,
                account_number=account_number,
                trigger_reason=reason,
                executed_at=datetime.utcnow(),
                estimated_impact=snapshot.total_market_value
            )

            # Get all open positions
            positions = await self._get_open_positions(account_number)

            exit_orders = []
            positions_closed = 0
            errors = []

            # Create market orders to close all positions
            for position in positions:
                try:
                    exit_order = await self._create_emergency_exit_order(position)
                    exit_orders.append(exit_order)
                    positions_closed += 1
                except Exception as e:
                    errors.append(f"Failed to close position {position['symbol']}: {str(e)}")

            # Update emergency action
            emergency_action.positions_affected = positions_closed
            emergency_action.success = len(errors) == 0
            emergency_action.metadata = {
                "exit_orders": [order["order_id"] for order in exit_orders],
                "portfolio_snapshot": snapshot.__dict__
            }

            # Store emergency action
            await self._store_emergency_action(emergency_action)

            # Send emergency notification
            await self._send_emergency_notification(
                account_number=account_number,
                notification_type="emergency_exit_executed",
                message=f"Emergency exit executed. {positions_closed} positions closed at market prices.",
                priority=AlertLevel.EMERGENCY
            )

            return EmergencyResponse(
                action_id=action_id,
                action_type=EmergencyActionType.EMERGENCY_EXIT,
                success=len(errors) == 0,
                message=f"Emergency exit executed. Closed {positions_closed} positions." +
                       (f" Errors: {'; '.join(errors)}" if errors else ""),
                positions_closed=positions_closed,
                estimated_impact=snapshot.total_market_value,
                recovery_instructions="Review executed trades and assess market impact."
            )

        except Exception as e:
            emergency_action = EmergencyAction(
                action_id=action_id,
                action_type=EmergencyActionType.EMERGENCY_EXIT,
                user_id=user_id,
                account_number=account_number,
                trigger_reason=reason,
                executed_at=datetime.utcnow(),
                success=False,
                error_message=str(e)
            )
            await self._store_emergency_action(emergency_action)

            return EmergencyResponse(
                action_id=action_id,
                action_type=EmergencyActionType.EMERGENCY_EXIT,
                success=False,
                message=f"Emergency exit failed: {str(e)}",
                recovery_instructions="Contact support immediately."
            )

    async def halt_trading(
        self,
        user_id: str,
        account_number: str,
        reason: str,
        override_required: bool = True
    ) -> TradingHalt:
        """Halt all trading for an account."""
        halt_id = str(uuid.uuid4())

        halt = TradingHalt(
            halt_id=halt_id,
            account_number=account_number,
            reason=reason,
            halted_at=datetime.utcnow(),
            halted_by=user_id,
            auto_halt=False,
            override_required=override_required
        )

        # Store trading halt in cache for immediate effect
        await self._store_trading_halt(halt)

        # Cancel all pending orders during halt
        await self.panic_button(user_id, account_number, f"Trading halt: {reason}")

        # Send notification
        await self._send_emergency_notification(
            account_number=account_number,
            notification_type="trading_halt",
            message=f"Trading halted: {reason}",
            priority=AlertLevel.CRITICAL
        )

        return halt

    async def resume_trading(
        self,
        user_id: str,
        account_number: str,
        halt_id: str,
        justification: str
    ) -> bool:
        """Resume trading after halt with proper authorization."""
        try:
            # Get existing halt
            halt = await self._get_trading_halt(account_number, halt_id)
            if not halt:
                return False

            # Update halt record
            halt.resumed_at = datetime.utcnow()
            halt.resumed_by = user_id

            # Remove halt from cache
            await self._remove_trading_halt(account_number)

            # Log the resume action
            emergency_action = EmergencyAction(
                action_id=str(uuid.uuid4()),
                action_type=EmergencyActionType.MANUAL_OVERRIDE,
                user_id=user_id,
                account_number=account_number,
                trigger_reason=f"Trading resumed: {justification}",
                executed_at=datetime.utcnow(),
                success=True,
                metadata={"halt_id": halt_id, "justification": justification}
            )
            await self._store_emergency_action(emergency_action)

            # Send notification
            await self._send_emergency_notification(
                account_number=account_number,
                notification_type="trading_resumed",
                message=f"Trading resumed by {user_id}: {justification}",
                priority=AlertLevel.WARNING
            )

            return True

        except Exception as e:
            print(f"Failed to resume trading: {e}")
            return False

    async def is_trading_halted(self, account_number: str) -> bool:
        """Check if trading is currently halted for an account."""
        try:
            halt_key = f"trading_halt:{account_number}"
            halt_data = await self.cache.get(halt_key)
            return halt_data is not None
        except Exception:
            return False

    # Helper methods
    async def _get_pending_orders(self, account_number: str) -> List[Dict[str, Any]]:
        """Get all pending orders for an account."""
        # Mock implementation - in real system, query from order service
        return [
            {"order_id": "order1", "symbol": "AAPL", "status": "pending"},
            {"order_id": "order2", "symbol": "MSFT", "status": "pending"}
        ]

    async def _cancel_order(self, order_id: str) -> bool:
        """Cancel a specific order."""
        # Mock implementation - in real system, call order management service
        await asyncio.sleep(0.1)  # Simulate API call
        return True

    async def _get_open_positions(self, account_number: str) -> List[Dict[str, Any]]:
        """Get all open positions for an account."""
        # Mock implementation - in real system, query from position service
        return [
            {"symbol": "AAPL", "quantity": 100, "side": "long"},
            {"symbol": "MSFT", "quantity": 50, "side": "long"}
        ]

    async def _create_emergency_exit_order(self, position: Dict[str, Any]) -> Dict[str, Any]:
        """Create market order to exit a position."""
        # Mock implementation - in real system, create actual market order
        return {
            "order_id": f"exit_{position['symbol']}_{uuid.uuid4().hex[:8]}",
            "symbol": position["symbol"],
            "side": "sell" if position["side"] == "long" else "buy",
            "quantity": abs(position["quantity"]),
            "order_type": "market"
        }

    async def _create_portfolio_snapshot(self, account_number: str) -> PortfolioSnapshot:
        """Create snapshot of portfolio before emergency action."""
        # Mock implementation - in real system, calculate from actual positions
        return PortfolioSnapshot(
            account_number=account_number,
            snapshot_time=datetime.utcnow(),
            total_market_value=Decimal("100000.00"),
            cash_balance=Decimal("25000.00"),
            total_pnl=Decimal("5000.00"),
            daily_pnl=Decimal("-1500.00"),
            unrealized_pnl=Decimal("2500.00"),
            position_count=5,
            open_order_count=3,
            concentration_risk_score=0.3,
            max_position_exposure=Decimal("30000.00")
        )

    async def _store_emergency_action(self, action: EmergencyAction) -> None:
        """Store emergency action in database and cache."""
        try:
            # Store in cache for immediate access
            cache_key = f"emergency_action:{action.action_id}"
            action_data = {
                "action_id": action.action_id,
                "action_type": action.action_type.value,
                "user_id": action.user_id,
                "account_number": action.account_number,
                "trigger_reason": action.trigger_reason,
                "executed_at": action.executed_at.isoformat(),
                "success": action.success,
                "orders_affected": action.orders_affected,
                "positions_affected": action.positions_affected
            }
            await self.cache.setex(cache_key, 86400, str(action_data))  # 24-hour expiry

            # In real implementation, also store in database
            # await self.session.add(action)
            # await self.session.commit()

        except Exception as e:
            print(f"Failed to store emergency action: {e}")

    async def _store_trading_halt(self, halt: TradingHalt) -> None:
        """Store trading halt status."""
        try:
            halt_key = f"trading_halt:{halt.account_number}"
            halt_data = {
                "halt_id": halt.halt_id,
                "reason": halt.reason,
                "halted_at": halt.halted_at.isoformat(),
                "halted_by": halt.halted_by,
                "override_required": halt.override_required
            }
            await self.cache.set(halt_key, str(halt_data))  # No expiry for active halts
        except Exception as e:
            print(f"Failed to store trading halt: {e}")

    async def _get_trading_halt(self, account_number: str, halt_id: str) -> Optional[TradingHalt]:
        """Get trading halt by ID."""
        try:
            halt_key = f"trading_halt:{account_number}"
            halt_data = await self.cache.get(halt_key)
            if halt_data:
                # In real implementation, parse JSON and return TradingHalt object
                return TradingHalt(
                    halt_id=halt_id,
                    account_number=account_number,
                    reason="Mock halt",
                    halted_at=datetime.utcnow(),
                    halted_by="system",
                    auto_halt=False
                )
            return None
        except Exception:
            return None

    async def _remove_trading_halt(self, account_number: str) -> None:
        """Remove trading halt from cache."""
        try:
            halt_key = f"trading_halt:{account_number}"
            await self.cache.delete(halt_key)
        except Exception as e:
            print(f"Failed to remove trading halt: {e}")

    async def _send_emergency_notification(
        self,
        account_number: str,
        notification_type: str,
        message: str,
        priority: AlertLevel
    ) -> None:
        """Send emergency notification to relevant parties."""
        try:
            notification = EmergencyNotification(
                notification_id=str(uuid.uuid4()),
                account_number=account_number,
                notification_type=notification_type,
                priority=priority,
                message=message,
                recipients=["user@example.com", "support@trading.com"],
                channels=["email", "webhook"]
            )

            # Store notification
            notification_key = f"emergency_notification:{notification.notification_id}"
            await self.cache.setex(notification_key, 86400, str(notification.__dict__))

            # In real implementation, send actual notifications via email, SMS, webhooks
            print(f"EMERGENCY NOTIFICATION [{priority.value.upper()}]: {message}")

        except Exception as e:
            print(f"Failed to send emergency notification: {e}")