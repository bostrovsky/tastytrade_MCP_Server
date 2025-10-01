"""Order management API endpoints."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession

from tastytrade_mcp.api.auth import get_current_user
from tastytrade_mcp.api.helpers import get_active_broker_link
from tastytrade_mcp.db.session import get_session
from tastytrade_mcp.models.order import (
    OrderSide, OrderType, OrderStatus, TimeInForce
)
from tastytrade_mcp.models.user import User
from tastytrade_mcp.services.order import (
    OrderPreviewService, OrderManagementService,
    ValidationError, PreviewExpiredError, ConfirmationError
)
from tastytrade_mcp.services.tastytrade import TastyTradeService
from tastytrade_mcp.utils.logging import get_logger

router = APIRouter(prefix="/orders", tags=["Orders"])
logger = get_logger(__name__)


# Request Models
class CreateOrderRequest(BaseModel):
    """Create order request model."""
    account_id: str = Field(..., description="Account ID")
    symbol: str = Field(..., description="Trading symbol", min_length=1, max_length=10)
    side: OrderSide = Field(..., description="Order side (buy/sell)")
    quantity: int = Field(..., description="Order quantity", gt=0, le=10000)
    order_type: OrderType = Field(..., description="Order type")
    price: Optional[Decimal] = Field(None, description="Limit price", ge=0)
    stop_price: Optional[Decimal] = Field(None, description="Stop price", ge=0)
    time_in_force: TimeInForce = Field(TimeInForce.DAY, description="Time in force")

    @validator("price")
    def validate_price(cls, v, values):
        order_type = values.get("order_type")
        if order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT] and not v:
            raise ValueError(f"{order_type.value} orders require a price")
        return v

    @validator("stop_price")
    def validate_stop_price(cls, v, values):
        order_type = values.get("order_type")
        if order_type in [OrderType.STOP, OrderType.STOP_LIMIT] and not v:
            raise ValueError(f"{order_type.value} orders require a stop price")
        return v

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class ConfirmOrderRequest(BaseModel):
    """Confirm order request model."""
    preview_token: str = Field(..., description="Preview token from create order")
    confirmation_code: str = Field(..., description="Must be 'CONFIRM'", pattern="^CONFIRM$")


class ModifyOrderRequest(BaseModel):
    """Modify order request model."""
    new_price: Optional[Decimal] = Field(None, description="New limit price", ge=0)
    new_quantity: Optional[int] = Field(None, description="New quantity", gt=0, le=10000)

    @validator("new_quantity")
    def validate_modification(cls, v, values):
        if not v and not values.get("new_price"):
            raise ValueError("Must specify new price or quantity")
        return v

    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }


class CancelOrderRequest(BaseModel):
    """Cancel order request model."""
    reason: Optional[str] = Field(None, description="Cancellation reason", max_length=255)


# Response Models
class OrderPreviewResponse(BaseModel):
    """Order preview response model."""
    preview_token: str = Field(..., description="Preview token (expires in 2 minutes)")
    symbol: str
    side: str
    quantity: int
    order_type: str
    price: Optional[float]
    stop_price: Optional[float]
    time_in_force: str
    estimated_cost: float
    risk_assessment: dict
    current_quote: dict
    market_status: dict
    expires_at: datetime
    warnings: List[str] = Field(default_factory=list)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class OrderResponse(BaseModel):
    """Order response model."""
    id: str
    account_id: str
    external_order_id: Optional[str]
    symbol: str
    side: str
    quantity: int
    filled_quantity: int
    order_type: str
    price: Optional[float]
    stop_price: Optional[float]
    average_fill_price: Optional[float]
    time_in_force: str
    status: str
    submitted_at: Optional[datetime]
    filled_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    cancelled_reason: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class OrderListResponse(BaseModel):
    """Order list response model."""
    orders: List[OrderResponse]
    count: int
    has_more: bool


# API Endpoints
@router.post("/preview", response_model=OrderPreviewResponse)
async def create_order_preview(
    request: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderPreviewResponse:
    """
    Create order preview for two-step confirmation.

    Returns a preview token valid for 2 minutes that must be confirmed.
    """
    # Get broker link
    broker_link = await get_active_broker_link(session, current_user)

    if not broker_link:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active TastyTrade account linked"
        )

    try:
        # Initialize services
        tastytrade = TastyTradeService(session)
        preview_service = OrderPreviewService(session, tastytrade)

        # Create preview
        preview = await preview_service.create_preview(
            user=current_user,
            account_id=request.account_id,
            symbol=request.symbol.upper(),
            side=request.side,
            quantity=request.quantity,
            order_type=request.order_type,
            price=request.price,
            stop_price=request.stop_price,
            time_in_force=request.time_in_force,
            broker_link=broker_link
        )

        # Prepare response
        market_status = preview.risk_assessment.get("market_status", {})
        warnings = preview.risk_assessment.get("warnings", [])

        if preview.risk_assessment.get("risk_level") == "HIGH":
            warnings.insert(0, "⚠️ HIGH RISK: Review warnings carefully before confirming")

        return OrderPreviewResponse(
            preview_token=preview.preview_token,
            symbol=preview.symbol,
            side=preview.side.value,
            quantity=preview.quantity,
            order_type=preview.order_type.value,
            price=float(preview.price) if preview.price else None,
            stop_price=float(preview.stop_price) if preview.stop_price else None,
            time_in_force=preview.time_in_force.value,
            estimated_cost=float(preview.estimated_cost),
            risk_assessment=preview.risk_assessment,
            current_quote=preview.quote_data or {},
            market_status=market_status,
            expires_at=preview.expires_at,
            warnings=warnings
        )

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create order preview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create order preview"
        )


@router.post("/confirm", response_model=OrderResponse)
async def confirm_order(
    request: ConfirmOrderRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderResponse:
    """
    Confirm and submit order from preview.

    Requires typing 'CONFIRM' as confirmation code.
    """
    # Get broker link
    broker_link = await get_active_broker_link(session, current_user)

    if not broker_link:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active TastyTrade account linked"
        )

    try:
        # Initialize services
        tastytrade = TastyTradeService(session)
        preview_service = OrderPreviewService(session, tastytrade)

        # Confirm and submit order
        order = await preview_service.confirm_order(
            preview_token=request.preview_token,
            confirmation_code=request.confirmation_code,
            broker_link=broker_link
        )

        return OrderResponse(
            id=str(order.id),
            account_id=str(order.account_id),
            external_order_id=order.external_order_id,
            symbol=order.symbol,
            side=order.side.value,
            quantity=order.quantity,
            filled_quantity=order.filled_quantity,
            order_type=order.order_type.value,
            price=float(order.price) if order.price else None,
            stop_price=float(order.stop_price) if order.stop_price else None,
            average_fill_price=float(order.average_fill_price) if order.average_fill_price else None,
            time_in_force=order.time_in_force.value,
            status=order.status.value,
            submitted_at=order.submitted_at,
            filled_at=order.filled_at,
            cancelled_at=order.cancelled_at,
            cancelled_reason=order.cancelled_reason,
            created_at=order.created_at,
            updated_at=order.updated_at
        )

    except (PreviewExpiredError, ConfirmationError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to confirm order: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit order"
        )


@router.get("/", response_model=OrderListResponse)
async def list_orders(
    account_id: Optional[str] = Query(None, description="Filter by account ID"),
    status: Optional[OrderStatus] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderListResponse:
    """
    List orders with optional filters.

    Returns recent orders for the authenticated user.
    """
    try:
        # Initialize service
        tastytrade = TastyTradeService(session)
        order_service = OrderManagementService(session, tastytrade)

        # Get orders
        orders = await order_service.get_orders(
            user=current_user,
            account_id=account_id,
            status=status,
            limit=limit + 1  # Get one extra to check if there are more
        )

        has_more = len(orders) > limit
        if has_more:
            orders = orders[:limit]

        # Convert to response
        order_responses = []
        for order in orders:
            order_responses.append(OrderResponse(
                id=str(order.id),
                account_id=str(order.account_id),
                external_order_id=order.external_order_id,
                symbol=order.symbol,
                side=order.side.value,
                quantity=order.quantity,
                filled_quantity=order.filled_quantity,
                order_type=order.order_type.value,
                price=float(order.price) if order.price else None,
                stop_price=float(order.stop_price) if order.stop_price else None,
                average_fill_price=float(order.average_fill_price) if order.average_fill_price else None,
                time_in_force=order.time_in_force.value,
                status=order.status.value,
                submitted_at=order.submitted_at,
                filled_at=order.filled_at,
                cancelled_at=order.cancelled_at,
                cancelled_reason=order.cancelled_reason,
                created_at=order.created_at,
                updated_at=order.updated_at
            ))

        return OrderListResponse(
            orders=order_responses,
            count=len(order_responses),
            has_more=has_more
        )

    except Exception as e:
        logger.error(f"Failed to list orders: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve orders"
        )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderResponse:
    """Get specific order details."""
    try:
        # Initialize service
        tastytrade = TastyTradeService(session)
        order_service = OrderManagementService(session, tastytrade)

        # Get order
        order = await order_service.get_order(order_id, current_user)

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )

        return OrderResponse(
            id=str(order.id),
            account_id=str(order.account_id),
            external_order_id=order.external_order_id,
            symbol=order.symbol,
            side=order.side.value,
            quantity=order.quantity,
            filled_quantity=order.filled_quantity,
            order_type=order.order_type.value,
            price=float(order.price) if order.price else None,
            stop_price=float(order.stop_price) if order.stop_price else None,
            average_fill_price=float(order.average_fill_price) if order.average_fill_price else None,
            time_in_force=order.time_in_force.value,
            status=order.status.value,
            submitted_at=order.submitted_at,
            filled_at=order.filled_at,
            cancelled_at=order.cancelled_at,
            cancelled_reason=order.cancelled_reason,
            created_at=order.created_at,
            updated_at=order.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get order: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve order"
        )


@router.patch("/{order_id}", response_model=OrderResponse)
async def modify_order(
    order_id: str,
    request: ModifyOrderRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderResponse:
    """
    Modify an existing order.

    Can modify price and/or quantity for working orders.
    """
    # Get broker link
    broker_link = await get_active_broker_link(session, current_user)

    if not broker_link:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active TastyTrade account linked"
        )

    try:
        # Initialize service
        tastytrade = TastyTradeService(session)
        order_service = OrderManagementService(session, tastytrade)

        # Modify order
        order = await order_service.modify_order(
            order_id=order_id,
            user=current_user,
            new_price=request.new_price,
            new_quantity=request.new_quantity,
            broker_link=broker_link
        )

        return OrderResponse(
            id=str(order.id),
            account_id=str(order.account_id),
            external_order_id=order.external_order_id,
            symbol=order.symbol,
            side=order.side.value,
            quantity=order.quantity,
            filled_quantity=order.filled_quantity,
            order_type=order.order_type.value,
            price=float(order.price) if order.price else None,
            stop_price=float(order.stop_price) if order.stop_price else None,
            average_fill_price=float(order.average_fill_price) if order.average_fill_price else None,
            time_in_force=order.time_in_force.value,
            status=order.status.value,
            submitted_at=order.submitted_at,
            filled_at=order.filled_at,
            cancelled_at=order.cancelled_at,
            cancelled_reason=order.cancelled_reason,
            created_at=order.created_at,
            updated_at=order.updated_at
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to modify order: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to modify order"
        )


@router.delete("/{order_id}", response_model=OrderResponse)
async def cancel_order(
    order_id: str,
    request: CancelOrderRequest = CancelOrderRequest(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrderResponse:
    """
    Cancel an existing order.

    Works for pending, submitted, or working orders.
    """
    # Get broker link
    broker_link = await get_active_broker_link(session, current_user)

    if not broker_link:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active TastyTrade account linked"
        )

    try:
        # Initialize service
        tastytrade = TastyTradeService(session)
        order_service = OrderManagementService(session, tastytrade)

        # Cancel order
        order = await order_service.cancel_order(
            order_id=order_id,
            user=current_user,
            reason=request.reason,
            broker_link=broker_link
        )

        return OrderResponse(
            id=str(order.id),
            account_id=str(order.account_id),
            external_order_id=order.external_order_id,
            symbol=order.symbol,
            side=order.side.value,
            quantity=order.quantity,
            filled_quantity=order.filled_quantity,
            order_type=order.order_type.value,
            price=float(order.price) if order.price else None,
            stop_price=float(order.stop_price) if order.stop_price else None,
            average_fill_price=float(order.average_fill_price) if order.average_fill_price else None,
            time_in_force=order.time_in_force.value,
            status=order.status.value,
            submitted_at=order.submitted_at,
            filled_at=order.filled_at,
            cancelled_at=order.cancelled_at,
            cancelled_reason=order.cancelled_reason,
            created_at=order.created_at,
            updated_at=order.updated_at
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to cancel order: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel order"
        )