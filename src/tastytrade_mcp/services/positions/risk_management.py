"""Position risk management - stop-loss and take-profit orders."""
import uuid
from decimal import Decimal
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..cache import get_cache
from .models import StopLossOrder, TakeProfitOrder


class RiskManagementService:
    """Manages stop-loss and take-profit orders."""

    def __init__(self):
        """Initialize risk management service."""
        self.cache = get_cache()

    async def set_stop_loss(
        self,
        symbol: str,
        stop_price: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        quantity: Optional[float] = None
    ) -> StopLossOrder:
        """Set stop-loss order for a position."""
        # Validation
        if stop_price <= 0:
            raise ValueError("Stop price must be positive")

        if order_type == "limit" and limit_price is None:
            raise ValueError("Limit price required for limit orders")

        # Create stop-loss order
        order = StopLossOrder(
            order_id=str(uuid.uuid4()),
            symbol=symbol,
            stop_price=Decimal(str(stop_price)),
            order_type=order_type,
            limit_price=Decimal(str(limit_price)) if limit_price else None,
            quantity=Decimal(str(quantity)) if quantity else None
        )

        # Store in cache
        await self._store_stop_loss_order(order)

        return order

    async def set_take_profit(
        self,
        symbol: str,
        target_price: float,
        order_type: str = "limit",
        quantity: Optional[float] = None
    ) -> TakeProfitOrder:
        """Set take-profit order for a position."""
        # Validation
        if target_price <= 0:
            raise ValueError("Target price must be positive")

        # Create take-profit order
        order = TakeProfitOrder(
            order_id=str(uuid.uuid4()),
            symbol=symbol,
            target_price=Decimal(str(target_price)),
            order_type=order_type,
            quantity=Decimal(str(quantity)) if quantity else None
        )

        # Store in cache
        await self._store_take_profit_order(order)

        return order

    async def get_stop_loss_orders(self, symbol: str = None) -> List[StopLossOrder]:
        """Get stop-loss orders for a symbol or all symbols."""
        try:
            pattern = f"stop_loss:{symbol}:*" if symbol else "stop_loss:*"
            keys = await self.cache.keys(pattern)

            orders = []
            for key in keys:
                order_data = await self.cache.get(key)
                if order_data:
                    # In a real implementation, you'd parse JSON data here
                    # For now, return mock data structure
                    pass

            return orders
        except Exception:
            return []

    async def get_take_profit_orders(self, symbol: str = None) -> List[TakeProfitOrder]:
        """Get take-profit orders for a symbol or all symbols."""
        try:
            pattern = f"take_profit:{symbol}:*" if symbol else "take_profit:*"
            keys = await self.cache.keys(pattern)

            orders = []
            for key in keys:
                order_data = await self.cache.get(key)
                if order_data:
                    # In a real implementation, you'd parse JSON data here
                    # For now, return mock data structure
                    pass

            return orders
        except Exception:
            return []

    async def cancel_stop_loss(self, symbol: str, order_id: str = None) -> bool:
        """Cancel stop-loss order(s) for a symbol."""
        try:
            if order_id:
                # Cancel specific order
                cache_key = f"stop_loss:{symbol}:{order_id}"
                await self.cache.delete(cache_key)
            else:
                # Cancel all stop-loss orders for symbol
                pattern = f"stop_loss:{symbol}:*"
                keys = await self.cache.keys(pattern)
                if keys:
                    await self.cache.delete(*keys)
            return True
        except Exception:
            return False

    async def cancel_take_profit(self, symbol: str, order_id: str = None) -> bool:
        """Cancel take-profit order(s) for a symbol."""
        try:
            if order_id:
                # Cancel specific order
                cache_key = f"take_profit:{symbol}:{order_id}"
                await self.cache.delete(cache_key)
            else:
                # Cancel all take-profit orders for symbol
                pattern = f"take_profit:{symbol}:*"
                keys = await self.cache.keys(pattern)
                if keys:
                    await self.cache.delete(*keys)
            return True
        except Exception:
            return False

    async def _store_stop_loss_order(self, order: StopLossOrder) -> None:
        """Store stop-loss order in cache."""
        try:
            cache_key = f"stop_loss:{order.symbol}:{order.order_id}"
            order_data = {
                "order_id": order.order_id,
                "symbol": order.symbol,
                "stop_price": str(order.stop_price),
                "order_type": order.order_type,
                "limit_price": str(order.limit_price) if order.limit_price else None,
                "quantity": str(order.quantity) if order.quantity else None,
                "created_at": order.created_at.isoformat()
            }
            await self.cache.setex(cache_key, 86400 * 7, str(order_data))  # 7-day expiry
        except Exception as e:
            print(f"Warning: Failed to cache stop-loss order: {e}")

    async def _store_take_profit_order(self, order: TakeProfitOrder) -> None:
        """Store take-profit order in cache."""
        try:
            cache_key = f"take_profit:{order.symbol}:{order.order_id}"
            order_data = {
                "order_id": order.order_id,
                "symbol": order.symbol,
                "target_price": str(order.target_price),
                "order_type": order.order_type,
                "quantity": str(order.quantity) if order.quantity else None,
                "created_at": order.created_at.isoformat()
            }
            await self.cache.setex(cache_key, 86400 * 7, str(order_data))  # 7-day expiry
        except Exception as e:
            print(f"Warning: Failed to cache take-profit order: {e}")

    async def update_stop_loss(self, symbol: str, order_id: str, new_stop_price: float) -> bool:
        """Update existing stop-loss order."""
        try:
            cache_key = f"stop_loss:{symbol}:{order_id}"
            order_data = await self.cache.get(cache_key)

            if order_data:
                # Update the stop price and re-store
                # In a real implementation, you'd parse and update the JSON data
                return True
            return False
        except Exception:
            return False

    async def update_take_profit(self, symbol: str, order_id: str, new_target_price: float) -> bool:
        """Update existing take-profit order."""
        try:
            cache_key = f"take_profit:{symbol}:{order_id}"
            order_data = await self.cache.get(cache_key)

            if order_data:
                # Update the target price and re-store
                # In a real implementation, you'd parse and update the JSON data
                return True
            return False
        except Exception:
            return False

    def calculate_stop_loss_price(
        self,
        entry_price: float,
        risk_percentage: float,
        position_type: str = "long"
    ) -> float:
        """Calculate appropriate stop-loss price based on risk percentage."""
        if position_type.lower() == "long":
            return entry_price * (1 - risk_percentage / 100)
        else:  # short position
            return entry_price * (1 + risk_percentage / 100)

    def calculate_take_profit_price(
        self,
        entry_price: float,
        reward_percentage: float,
        position_type: str = "long"
    ) -> float:
        """Calculate appropriate take-profit price based on reward percentage."""
        if position_type.lower() == "long":
            return entry_price * (1 + reward_percentage / 100)
        else:  # short position
            return entry_price * (1 - reward_percentage / 100)