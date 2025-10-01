"""Order management service."""
import secrets
from datetime import datetime, timedelta, time
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID

import pytz
from sqlalchemy import select, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tastytrade_mcp.models.order import (
    Order, OrderEvent, BracketOrder,
    OrderSide, OrderType, OrderStatus, OrderEventType, TimeInForce
)
from tastytrade_mcp.models.trading import OrderPreview
from tastytrade_mcp.models.user import User
from tastytrade_mcp.services.tastytrade import TastyTradeService
from tastytrade_mcp.services.risk import RiskValidator
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class ValidationError(Exception):
    """Order validation error."""
    pass


class PreviewExpiredError(Exception):
    """Order preview expired error."""
    pass


class ConfirmationError(Exception):
    """Order confirmation error."""
    pass


class RiskViolationError(Exception):
    """Risk violation error."""
    pass


class OrderValidator:
    """Order validation service."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def validate_order_request(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType,
        price: Optional[Decimal],
        stop_price: Optional[Decimal],
        account_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate order request against account constraints."""
        validations = []

        # Symbol validation
        if not symbol or len(symbol) > 10:
            validations.append("Invalid symbol format")

        # Quantity validation
        if quantity <= 0:
            validations.append("Quantity must be positive")
        if quantity > 10000:
            validations.append("Quantity exceeds maximum allowed (10000)")

        # Price validations based on order type
        if order_type == OrderType.LIMIT and not price:
            validations.append("Limit orders require a price")
        if order_type == OrderType.STOP and not stop_price:
            validations.append("Stop orders require a stop price")
        if order_type == OrderType.STOP_LIMIT and (not price or not stop_price):
            validations.append("Stop-limit orders require both price and stop price")

        # Price sanity checks
        if price and price <= 0:
            validations.append("Price must be positive")
        if stop_price and stop_price <= 0:
            validations.append("Stop price must be positive")

        # Market hours validation
        market_status = self._check_market_hours()
        if not market_status["is_open"] and order_type == OrderType.MARKET:
            validations.append(f"Market orders not allowed during {market_status['session']}")

        # Buying power validation
        if account_data:
            buying_power = Decimal(str(account_data.get("buying_power", 0)))
            if side in [OrderSide.BUY, OrderSide.BUY_TO_COVER]:
                estimated_cost = self._estimate_cost(quantity, price, order_type)
                if estimated_cost > buying_power:
                    validations.append(f"Insufficient buying power (need ${estimated_cost}, have ${buying_power})")

        if validations:
            raise ValidationError("; ".join(validations))

        return {
            "valid": True,
            "market_status": market_status,
            "warnings": []
        }

    def _check_market_hours(self) -> Dict[str, Any]:
        """Check if market is open."""
        et_tz = pytz.timezone('US/Eastern')
        now_et = datetime.now(et_tz)
        current_time = now_et.time()
        weekday = now_et.weekday()

        # Market closed on weekends
        if weekday >= 5:
            return {"is_open": False, "session": "CLOSED", "next_open": "Monday 9:30 AM ET"}

        # Define market hours (ET)
        pre_market_start = time(4, 0)
        regular_start = time(9, 30)
        regular_end = time(16, 0)
        after_hours_end = time(20, 0)

        if current_time < pre_market_start:
            return {"is_open": False, "session": "CLOSED", "next_open": "4:00 AM ET"}
        elif current_time < regular_start:
            return {"is_open": True, "session": "PRE_MARKET", "regular_open": "9:30 AM ET"}
        elif current_time < regular_end:
            return {"is_open": True, "session": "REGULAR", "close": "4:00 PM ET"}
        elif current_time < after_hours_end:
            return {"is_open": True, "session": "AFTER_HOURS", "close": "8:00 PM ET"}
        else:
            return {"is_open": False, "session": "CLOSED", "next_open": "4:00 AM ET tomorrow"}

    def _estimate_cost(
        self,
        quantity: int,
        price: Optional[Decimal],
        order_type: OrderType
    ) -> Decimal:
        """Estimate order cost."""
        if order_type == OrderType.MARKET:
            # Use a buffer for market orders (assume 1% slippage)
            estimated_price = price * Decimal("1.01") if price else Decimal("100")
        else:
            estimated_price = price or Decimal("100")

        return Decimal(quantity) * estimated_price


class OrderPreviewService:
    """Order preview service for two-step confirmation."""

    def __init__(self, session: AsyncSession, tastytrade: TastyTradeService):
        self.session = session
        self.tastytrade = tastytrade
        self.validator = OrderValidator(session)
        self.risk_validator = RiskValidator(session)

    async def create_preview(
        self,
        user: User,
        account_id: str,
        symbol: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        time_in_force: TimeInForce = TimeInForce.DAY,
        broker_link: Any = None
    ) -> OrderPreview:
        """Create order preview with validation and risk assessment."""
        try:
            # Get account data for validation
            account_data = {}
            if broker_link:
                try:
                    balances = await self.tastytrade.get_balances(broker_link, account_id)
                    account_data["buying_power"] = balances.get("cash-available-for-trading", 0)
                except Exception as e:
                    logger.warning(f"Failed to fetch account data: {e}")

            # Validate order parameters
            validation_result = await self.validator.validate_order_request(
                symbol, side, quantity, order_type, price, stop_price, account_data
            )

            # Perform risk validation
            trade_request = {
                "symbol": symbol,
                "quantity": quantity,
                "side": side.value,
                "order_type": order_type.value,
                "price": float(price) if price else None,
                "stop_price": float(stop_price) if stop_price else None,
                "account_number": account_id  # Using account_id as account_number
            }

            risk_result = await self.risk_validator.validate_trade(
                trade_request,
                account_id,  # Using account_id as account_number
                user.id
            )

            if not risk_result.approved:
                # Log risk violations
                logger.warning(
                    f"Trade blocked by risk validation: {symbol} {side.value} {quantity} - "
                    f"Violations: {[v.message for v in risk_result.violations]}"
                )
                # Include risk violations in the validation error
                validation_errors = validation_result.get("errors", []) if isinstance(validation_result, dict) else []
                for violation in risk_result.violations:
                    validation_errors.append(f"Risk violation: {violation.message}")
                if validation_errors:
                    raise ValidationError("Risk validation failed", {"errors": validation_errors})

            # Get real-time quote
            quote_data = {}
            if broker_link:
                try:
                    quotes = await self.tastytrade.get_market_data(broker_link, [symbol])
                    if quotes and quotes.get("items"):
                        quote_data = quotes["items"][0]
                except Exception as e:
                    logger.warning(f"Failed to fetch quote: {e}")

            # Calculate estimated cost
            current_price = Decimal(str(quote_data.get("last", price or 100)))
            if order_type == OrderType.MARKET:
                estimated_price = current_price
            else:
                estimated_price = price or current_price

            estimated_cost = Decimal(quantity) * estimated_price

            # Perform risk assessment
            risk_assessment = self._assess_risk(
                symbol, side, quantity, estimated_cost, account_data
            )

            # Add any risk warnings to the assessment
            if risk_result.warnings:
                if not risk_assessment:
                    risk_assessment = {}
                risk_assessment["warnings"] = [
                    {"rule": w.rule_name, "message": w.message}
                    for w in risk_result.warnings
                ]

            # Generate nonce for two-step confirmation
            nonce = secrets.token_urlsafe(32)

            # Create preview record using the trading.py OrderPreview structure
            order_data = {
                "symbol": symbol,
                "side": side.value if isinstance(side, Enum) else side,
                "quantity": quantity,
                "order_type": order_type.value if isinstance(order_type, Enum) else order_type,
                "price": float(price) if price else None,
                "stop_price": float(stop_price) if stop_price else None,
                "time_in_force": time_in_force.value if isinstance(time_in_force, Enum) else time_in_force,
                "risk_assessment": risk_assessment,
                "quote_data": quote_data
            }

            # Get user_id before any potential session issues
            user_id = user.id

            preview = OrderPreview(
                user_id=user_id,
                account_number=account_id,  # This is already a string
                order_json=order_data,
                estimated_cost=float(estimated_cost) if estimated_cost else None,
                nonce=nonce,
                expires_at=datetime.utcnow() + timedelta(minutes=2)
            )

            self.session.add(preview)
            await self.session.commit()

            return preview

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to create order preview: {e}", exc_info=True)
            raise

    def _assess_risk(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        estimated_cost: Decimal,
        account_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Assess order risk."""
        risk_level = "LOW"
        warnings = []

        # Check position concentration
        if account_data:
            nlv = Decimal(str(account_data.get("net_liquidating_value", estimated_cost)))
            if nlv > 0:
                position_percent = (estimated_cost / nlv) * 100
                if position_percent > 20:
                    risk_level = "HIGH"
                    warnings.append(f"Position would be {position_percent:.1f}% of account")
                elif position_percent > 10:
                    risk_level = "MEDIUM"
                    warnings.append(f"Position would be {position_percent:.1f}% of account")

        # Check for large orders
        if quantity > 1000:
            warnings.append("Large order size may impact market price")
            if risk_level == "LOW":
                risk_level = "MEDIUM"

        # Check for penny stocks
        if estimated_cost / quantity < 5:
            warnings.append("Low-priced stock - higher volatility risk")
            if risk_level == "LOW":
                risk_level = "MEDIUM"

        return {
            "risk_level": risk_level,
            "warnings": warnings,
            "position_size_percent": float(position_percent) if account_data else None,
            "estimated_impact": float(estimated_cost)
        }

    async def confirm_order(
        self,
        preview_token: str,
        confirmation_code: str,
        broker_link: Any
    ) -> Order:
        """Confirm and submit order from preview."""
        if confirmation_code != "CONFIRM":
            raise ConfirmationError("Invalid confirmation code. Type 'CONFIRM' to execute")

        # Fetch preview
        stmt = select(OrderPreview).where(OrderPreview.preview_token == preview_token)
        result = await self.session.execute(stmt)
        preview = result.scalar_one_or_none()

        if not preview:
            raise PreviewExpiredError("Order preview not found")

        if preview.expires_at < datetime.utcnow():
            raise PreviewExpiredError("Order preview has expired. Please create a new order")

        # Final risk check
        if preview.risk_assessment.get("risk_level") == "HIGH":
            warnings = preview.risk_assessment.get("warnings", [])
            if warnings:
                logger.warning(f"High risk order submitted: {warnings}")

        try:
            # Submit order to TastyTrade
            order_request = {
                "symbol": preview.symbol,
                "side": preview.side.value,
                "quantity": preview.quantity,
                "order_type": preview.order_type.value,
                "time_in_force": preview.time_in_force.value if preview.time_in_force else "day"
            }

            if preview.price:
                order_request["price"] = str(preview.price)
            if preview.stop_price:
                order_request["stop_price"] = str(preview.stop_price)

            external_order = await self.tastytrade.submit_order(
                broker_link,
                str(preview.account_id),
                order_request
            )

            # Create internal order record
            order = Order(
                account_id=preview.account_id,
                user_id=preview.user_id,
                external_order_id=external_order.get("id"),
                preview_token=preview.preview_token,
                symbol=preview.symbol,
                side=preview.side,
                quantity=preview.quantity,
                order_type=preview.order_type,
                price=preview.price,
                stop_price=preview.stop_price,
                time_in_force=preview.time_in_force,
                status=OrderStatus.SUBMITTED,
                submitted_at=datetime.utcnow()
            )

            self.session.add(order)

            # Create order event
            event = OrderEvent(
                order_id=order.id,
                event_type=OrderEventType.SUBMITTED,
                event_data={
                    "external_order_id": external_order.get("id"),
                    "preview_token": preview.preview_token
                }
            )
            self.session.add(event)

            await self.session.commit()

            return order

        except Exception as e:
            logger.error(f"Failed to submit order: {e}", exc_info=True)
            await self.session.rollback()
            raise


class OrderManagementService:
    """Order management service for modifications and cancellations."""

    def __init__(self, session: AsyncSession, tastytrade: TastyTradeService):
        self.session = session
        self.tastytrade = tastytrade

    async def get_orders(
        self,
        user: User,
        account_id: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 100
    ) -> List[Order]:
        """Get orders for user with optional filters."""
        stmt = select(Order).where(Order.user_id == user.id)

        if account_id:
            stmt = stmt.where(Order.account_id == UUID(account_id))

        if status:
            stmt = stmt.where(Order.status == status)

        stmt = stmt.order_by(Order.created_at.desc()).limit(limit)
        stmt = stmt.options(selectinload(Order.events))

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_order(self, order_id: str, user: User) -> Optional[Order]:
        """Get specific order by ID."""
        stmt = select(Order).where(
            and_(
                Order.id == UUID(order_id),
                Order.user_id == user.id
            )
        ).options(selectinload(Order.events))

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def modify_order(
        self,
        order_id: str,
        user: User,
        new_price: Optional[Decimal] = None,
        new_quantity: Optional[int] = None,
        broker_link: Any = None
    ) -> Order:
        """Modify an existing order."""
        order = await self.get_order(order_id, user)
        if not order:
            raise ValueError("Order not found")

        if order.status not in [OrderStatus.SUBMITTED, OrderStatus.ACCEPTED, OrderStatus.WORKING]:
            raise ValueError(f"Cannot modify order in {order.status.value} status")

        if not new_price and not new_quantity:
            raise ValueError("Must specify new price or quantity")

        try:
            # Submit modification to TastyTrade
            modification_request = {}
            if new_price:
                modification_request["price"] = str(new_price)
            if new_quantity:
                modification_request["quantity"] = new_quantity

            await self.tastytrade.modify_order(
                broker_link,
                str(order.account_id),
                order.external_order_id,
                modification_request
            )

            # Update order record
            if new_price:
                order.price = new_price
            if new_quantity:
                order.quantity = new_quantity

            # Create modification event
            event = OrderEvent(
                order_id=order.id,
                event_type=OrderEventType.MODIFIED,
                event_data={
                    "new_price": float(new_price) if new_price else None,
                    "new_quantity": new_quantity
                }
            )
            self.session.add(event)

            await self.session.commit()

            return order

        except Exception as e:
            logger.error(f"Failed to modify order: {e}", exc_info=True)
            await self.session.rollback()
            raise

    async def cancel_order(
        self,
        order_id: str,
        user: User,
        reason: Optional[str] = None,
        broker_link: Any = None
    ) -> Order:
        """Cancel an existing order."""
        order = await self.get_order(order_id, user)
        if not order:
            raise ValueError("Order not found")

        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            raise ValueError(f"Cannot cancel order in {order.status.value} status")

        try:
            # Submit cancellation to TastyTrade
            await self.tastytrade.cancel_order(
                broker_link,
                str(order.account_id),
                order.external_order_id
            )

            # Update order record
            order.status = OrderStatus.CANCELLED
            order.cancelled_at = datetime.utcnow()
            order.cancelled_reason = reason or "User requested"

            # Create cancellation event
            event = OrderEvent(
                order_id=order.id,
                event_type=OrderEventType.CANCELLED,
                event_data={"reason": reason}
            )
            self.session.add(event)

            await self.session.commit()

            return order

        except Exception as e:
            logger.error(f"Failed to cancel order: {e}", exc_info=True)
            await self.session.rollback()
            raise

    async def update_order_status(
        self,
        external_order_id: str,
        status: OrderStatus,
        filled_quantity: Optional[int] = None,
        average_fill_price: Optional[Decimal] = None
    ) -> Optional[Order]:
        """Update order status from broker webhook/polling."""
        stmt = select(Order).where(Order.external_order_id == external_order_id)
        result = await self.session.execute(stmt)
        order = result.scalar_one_or_none()

        if not order:
            return None

        order.status = status

        if filled_quantity:
            order.filled_quantity = filled_quantity

        if average_fill_price:
            order.average_fill_price = average_fill_price

        if status == OrderStatus.FILLED:
            order.filled_at = datetime.utcnow()

        # Create status event
        event = OrderEvent(
            order_id=order.id,
            event_type=OrderEventType(status.value),
            event_data={
                "filled_quantity": filled_quantity,
                "average_fill_price": float(average_fill_price) if average_fill_price else None
            }
        )
        self.session.add(event)

        await self.session.commit()

        return order