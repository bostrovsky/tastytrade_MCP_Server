"""Sandbox trading environment service."""
import random
import uuid
import asyncio
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_
from sqlalchemy.orm import selectinload

from tastytrade_mcp.models.sandbox import (
    SandboxAccount, SandboxPosition, SandboxOrder, SandboxTransaction,
    SandboxMarketData, SandboxReset, SandboxConfiguration,
    SandboxMode, SandboxAccountStatus, SandboxOrderStatus
)
from tastytrade_mcp.models.user import User
from tastytrade_mcp.db.session import get_async_session

logger = logging.getLogger(__name__)


class SandboxService:
    """Core sandbox trading service."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_sandbox_account(
        self,
        user_id: uuid.UUID,
        account_number: Optional[str] = None,
        initial_balance: Decimal = Decimal('100000.00'),
        account_type: str = "margin"
    ) -> SandboxAccount:
        """Create a new sandbox account for a user."""
        if not account_number:
            account_number = f"SANDBOX_{uuid.uuid4().hex[:8].upper()}"

        sandbox_account = SandboxAccount(
            user_id=user_id,
            account_number=account_number,
            account_type=account_type,
            initial_balance=initial_balance,
            current_balance=initial_balance,
            buying_power=initial_balance * 2,  # 2:1 margin for margin accounts
            net_liquidating_value=initial_balance,
            status=SandboxAccountStatus.ACTIVE
        )

        self.session.add(sandbox_account)
        await self.session.commit()
        await self.session.refresh(sandbox_account)

        logger.info(f"Created sandbox account {account_number} for user {user_id}")
        return sandbox_account

    async def get_sandbox_account(
        self,
        account_id: Optional[uuid.UUID] = None,
        account_number: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None
    ) -> Optional[SandboxAccount]:
        """Get sandbox account by ID, account number, or user ID."""
        query = select(SandboxAccount)

        if account_id:
            query = query.where(SandboxAccount.id == account_id)
        elif account_number:
            query = query.where(SandboxAccount.account_number == account_number)
        elif user_id:
            query = query.where(SandboxAccount.user_id == user_id)
        else:
            raise ValueError("Must provide account_id, account_number, or user_id")

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_user_sandbox_accounts(self, user_id: uuid.UUID) -> List[SandboxAccount]:
        """Get all sandbox accounts for a user."""
        query = select(SandboxAccount).where(SandboxAccount.user_id == user_id)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def switch_mode(self, user_id: uuid.UUID, mode: SandboxMode) -> Dict[str, Any]:
        """Switch between sandbox and production modes."""
        # In a real implementation, this would update user session state
        # For now, we'll return status information

        sandbox_accounts = await self.get_user_sandbox_accounts(user_id)

        response = {
            "user_id": str(user_id),
            "mode": mode.value,
            "switched_at": datetime.utcnow().isoformat(),
            "sandbox_accounts_available": len(sandbox_accounts),
            "status": "success"
        }

        if mode == SandboxMode.SANDBOX:
            # Ensure user has at least one sandbox account
            if not sandbox_accounts:
                account = await self.create_sandbox_account(user_id)
                response["created_new_account"] = account.account_number
                response["sandbox_accounts_available"] = 1

            response["message"] = "Switched to sandbox mode - trades will be simulated"
        else:
            response["message"] = "Switched to production mode - trades will be real"
            response["warning"] = "Production trading involves real money and risk"

        return response

    async def reset_sandbox_account(
        self,
        account_id: uuid.UUID,
        user_id: uuid.UUID,
        reset_type: str = "full",
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reset sandbox account to initial state."""
        account = await self.get_sandbox_account(account_id=account_id)
        if not account or account.user_id != user_id:
            raise ValueError("Account not found or not owned by user")

        # Get current state for audit
        positions_count = len(account.positions) if account.positions else 0
        orders_count = len([o for o in (account.orders or []) if o.status == SandboxOrderStatus.PENDING])
        previous_balance = account.current_balance

        # Clear positions and pending orders
        if reset_type in ["full", "positions_only"]:
            await self.session.execute(
                delete(SandboxPosition).where(SandboxPosition.account_id == account_id)
            )
            await self.session.execute(
                update(SandboxOrder)
                .where(and_(
                    SandboxOrder.account_id == account_id,
                    SandboxOrder.status == SandboxOrderStatus.PENDING
                ))
                .values(status=SandboxOrderStatus.CANCELLED, cancelled_at=datetime.utcnow())
            )

        # Reset balance
        if reset_type in ["full", "balance_only"]:
            account.current_balance = account.initial_balance
            account.net_liquidating_value = account.initial_balance
            account.buying_power = account.initial_balance * 2

        # Update reset tracking
        account.reset_count += 1
        account.last_reset_at = datetime.utcnow()

        # Create reset audit record
        reset_record = SandboxReset(
            account_id=account_id,
            user_id=user_id,
            reset_type=reset_type,
            previous_balance=previous_balance,
            new_balance=account.current_balance,
            positions_cleared=positions_count,
            orders_cancelled=orders_count,
            reason=reason
        )
        self.session.add(reset_record)

        await self.session.commit()

        logger.info(f"Reset sandbox account {account.account_number} (type: {reset_type})")

        return {
            "account_number": account.account_number,
            "reset_type": reset_type,
            "reset_count": account.reset_count,
            "previous_balance": float(previous_balance),
            "new_balance": float(account.current_balance),
            "positions_cleared": positions_count,
            "orders_cancelled": orders_count,
            "reset_at": account.last_reset_at.isoformat(),
            "status": "completed"
        }

    async def get_account_summary(self, account_id: uuid.UUID) -> Dict[str, Any]:
        """Get comprehensive account summary."""
        query = select(SandboxAccount).options(
            selectinload(SandboxAccount.positions),
            selectinload(SandboxAccount.orders),
            selectinload(SandboxAccount.transactions)
        ).where(SandboxAccount.id == account_id)

        result = await self.session.execute(query)
        account = result.scalar_one_or_none()

        if not account:
            raise ValueError("Account not found")

        # Calculate portfolio metrics
        total_position_value = sum(pos.market_value for pos in account.positions)
        unrealized_pnl = sum(pos.unrealized_pnl for pos in account.positions)
        realized_pnl = sum(trans.amount for trans in account.transactions
                          if trans.transaction_type == "realized_pnl")

        pending_orders = [o for o in account.orders if o.status == SandboxOrderStatus.PENDING]

        return {
            "account_number": account.account_number,
            "account_type": account.account_type,
            "status": account.status.value,
            "balances": {
                "cash_balance": float(account.current_balance),
                "net_liquidating_value": float(account.net_liquidating_value),
                "buying_power": float(account.buying_power),
                "total_position_value": float(total_position_value)
            },
            "pnl": {
                "unrealized_pnl": float(unrealized_pnl),
                "realized_pnl": float(realized_pnl),
                "total_pnl": float(unrealized_pnl + realized_pnl)
            },
            "positions": {
                "count": len(account.positions),
                "positions": [self._format_position(pos) for pos in account.positions]
            },
            "orders": {
                "pending_count": len(pending_orders),
                "total_count": len(account.orders),
                "pending_orders": [self._format_order(order) for order in pending_orders[:10]]
            },
            "sandbox_info": {
                "is_educational_mode": account.is_educational_mode,
                "reset_count": account.reset_count,
                "last_reset": account.last_reset_at.isoformat() if account.last_reset_at else None
            },
            "updated_at": account.updated_at.isoformat()
        }

    def _format_position(self, position: SandboxPosition) -> Dict[str, Any]:
        """Format position for API response."""
        return {
            "symbol": position.symbol,
            "instrument_type": position.instrument_type,
            "quantity": float(position.quantity),
            "average_open_price": float(position.average_open_price),
            "current_price": float(position.current_price),
            "market_value": float(position.market_value),
            "unrealized_pnl": float(position.unrealized_pnl),
            "unrealized_pnl_percent": float(
                (position.unrealized_pnl / (position.average_open_price * position.quantity)) * 100
                if position.average_open_price and position.quantity else 0
            ),
            "greeks": {
                "delta": float(position.delta) if position.delta else None,
                "gamma": float(position.gamma) if position.gamma else None,
                "theta": float(position.theta) if position.theta else None,
                "vega": float(position.vega) if position.vega else None
            } if position.option_type else None,
            "opened_at": position.opened_at.isoformat()
        }

    def _format_order(self, order: SandboxOrder) -> Dict[str, Any]:
        """Format order for API response."""
        return {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side,
            "order_type": order.order_type,
            "quantity": float(order.quantity),
            "price": float(order.price) if order.price else None,
            "status": order.status.value,
            "filled_quantity": float(order.filled_quantity),
            "average_fill_price": float(order.average_fill_price) if order.average_fill_price else None,
            "submitted_at": order.submitted_at.isoformat(),
            "filled_at": order.filled_at.isoformat() if order.filled_at else None
        }


class SandboxOrderExecutor:
    """Handles realistic order execution simulation."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.sandbox_service = SandboxService(session)

    async def submit_order(
        self,
        account_id: uuid.UUID,
        symbol: str,
        side: str,
        quantity: Decimal,
        order_type: str = "market",
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """Submit an order for execution simulation."""
        # Generate unique order ID
        order_id = f"SBX_{uuid.uuid4().hex[:12].upper()}"

        # Get current market data for the symbol
        market_data = await self._get_or_create_market_data(symbol)

        # Create order record
        order = SandboxOrder(
            account_id=account_id,
            order_id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            status=SandboxOrderStatus.PENDING
        )

        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)

        # Schedule execution simulation
        asyncio.create_task(self._simulate_execution(order, market_data))

        logger.info(f"Submitted sandbox order {order_id}: {side} {quantity} {symbol}")

        return {
            "order_id": order_id,
            "status": "submitted",
            "symbol": symbol,
            "side": side,
            "quantity": float(quantity),
            "order_type": order_type,
            "estimated_execution_time_ms": random.randint(100, 1000),
            "submitted_at": order.submitted_at.isoformat()
        }

    async def _simulate_execution(self, order: SandboxOrder, market_data: SandboxMarketData):
        """Simulate realistic order execution with delays and slippage."""
        try:
            # Simulate execution delay
            delay_ms = random.randint(50, 500)
            await asyncio.sleep(delay_ms / 1000)

            # Determine execution price based on order type
            execution_price = await self._calculate_execution_price(order, market_data)

            if execution_price is None:
                # Order cannot be executed (e.g., limit price not reached)
                return

            # Apply slippage
            slippage_bps = random.randint(0, 20)  # 0-20 basis points
            slippage_factor = Decimal(str(1 + (slippage_bps / 10000)))

            if order.side == "buy":
                execution_price *= slippage_factor
            else:
                execution_price /= slippage_factor

            # Round to reasonable precision
            execution_price = execution_price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # Update order status
            async with self.session.begin():
                order.status = SandboxOrderStatus.FILLED
                order.filled_quantity = order.quantity
                order.average_fill_price = execution_price
                order.filled_at = datetime.utcnow()

                # Create transaction record
                commission = Decimal('1.00')  # Fixed commission for simulation
                total_cost = execution_price * order.quantity

                if order.side == "buy":
                    transaction_amount = -(total_cost + commission)
                else:
                    transaction_amount = total_cost - commission

                # Get account for balance update
                account = await self.sandbox_service.get_sandbox_account(account_id=order.account_id)

                transaction = SandboxTransaction(
                    account_id=order.account_id,
                    order_id=order.id,
                    transaction_type="trade",
                    symbol=order.symbol,
                    quantity=order.quantity if order.side == "buy" else -order.quantity,
                    price=execution_price,
                    amount=transaction_amount,
                    balance_before=account.current_balance,
                    balance_after=account.current_balance + transaction_amount,
                    description=f"{order.side.upper()} {order.quantity} {order.symbol} @ {execution_price}"
                )

                # Update account balance
                account.current_balance += transaction_amount

                # Update or create position
                await self._update_position(account, order, execution_price)

                self.session.add(transaction)
                await self.session.commit()

            logger.info(f"Executed sandbox order {order.order_id}: {order.quantity} @ {execution_price}")

        except Exception as e:
            logger.error(f"Error executing sandbox order {order.order_id}: {e}")
            async with self.session.begin():
                order.status = SandboxOrderStatus.REJECTED
                await self.session.commit()

    async def _calculate_execution_price(
        self,
        order: SandboxOrder,
        market_data: SandboxMarketData
    ) -> Optional[Decimal]:
        """Calculate execution price based on order type and market conditions."""
        if order.order_type == "market":
            return market_data.ask if order.side == "buy" else market_data.bid

        elif order.order_type == "limit":
            if order.side == "buy" and order.price >= market_data.ask:
                return market_data.ask
            elif order.side == "sell" and order.price <= market_data.bid:
                return market_data.bid
            else:
                return None  # Limit price not reached

        elif order.order_type == "stop":
            # Simplified stop logic - would be more complex in reality
            if order.side == "buy" and market_data.last >= order.stop_price:
                return market_data.ask
            elif order.side == "sell" and market_data.last <= order.stop_price:
                return market_data.bid
            else:
                return None

        return market_data.last  # Default fallback

    async def _update_position(
        self,
        account: SandboxAccount,
        order: SandboxOrder,
        execution_price: Decimal
    ):
        """Update position after order execution."""
        # Find existing position
        query = select(SandboxPosition).where(
            and_(
                SandboxPosition.account_id == account.id,
                SandboxPosition.symbol == order.symbol
            )
        )
        result = await self.session.execute(query)
        position = result.scalar_one_or_none()

        quantity_change = order.quantity if order.side == "buy" else -order.quantity

        if position:
            # Update existing position
            old_quantity = position.quantity
            new_quantity = old_quantity + quantity_change

            if new_quantity == 0:
                # Position closed
                await self.session.delete(position)
            else:
                # Update average price and quantity
                total_cost = (old_quantity * position.average_open_price) + (quantity_change * execution_price)
                position.quantity = new_quantity
                position.average_open_price = total_cost / new_quantity
                position.current_price = execution_price
                position.market_value = new_quantity * execution_price
                position.updated_at = datetime.utcnow()
        else:
            # Create new position
            if quantity_change != 0:
                position = SandboxPosition(
                    account_id=account.id,
                    symbol=order.symbol,
                    instrument_type="equity",  # Would determine from symbol in real implementation
                    quantity=quantity_change,
                    average_open_price=execution_price,
                    current_price=execution_price,
                    market_value=quantity_change * execution_price
                )
                self.session.add(position)

    async def _get_or_create_market_data(self, symbol: str) -> SandboxMarketData:
        """Get or create simulated market data for a symbol."""
        query = select(SandboxMarketData).where(SandboxMarketData.symbol == symbol)
        result = await self.session.execute(query)
        market_data = result.scalar_one_or_none()

        if not market_data:
            # Create simulated market data
            base_price = Decimal(str(random.uniform(50, 500)))  # Random base price
            spread = base_price * Decimal('0.001')  # 0.1% spread

            market_data = SandboxMarketData(
                symbol=symbol,
                bid=base_price - spread/2,
                ask=base_price + spread/2,
                last=base_price,
                open_price=base_price * Decimal(str(random.uniform(0.98, 1.02))),
                high=base_price * Decimal(str(random.uniform(1.00, 1.05))),
                low=base_price * Decimal(str(random.uniform(0.95, 1.00))),
                close=base_price * Decimal(str(random.uniform(0.99, 1.01))),
                volume=random.randint(100000, 10000000),
                volatility=Decimal(str(random.uniform(0.15, 0.40)))
            )

            self.session.add(market_data)
            await self.session.commit()
            await self.session.refresh(market_data)

        return market_data


# Factory function for dependency injection
async def get_sandbox_service() -> SandboxService:
    """Get sandbox service instance."""
    async with get_async_session() as session:
        return SandboxService(session)


async def get_sandbox_order_executor() -> SandboxOrderExecutor:
    """Get sandbox order executor instance."""
    async with get_async_session() as session:
        return SandboxOrderExecutor(session)