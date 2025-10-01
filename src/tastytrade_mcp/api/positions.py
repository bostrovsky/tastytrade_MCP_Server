"""Position management API endpoints."""
import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from tastytrade_mcp.api.auth import get_current_user
from tastytrade_mcp.api.helpers import get_active_broker_link
from tastytrade_mcp.db.session import get_session
from tastytrade_mcp.models.auth import BrokerLink, LinkStatus
from tastytrade_mcp.models.user import User
from tastytrade_mcp.services.tastytrade import TastyTradeService
from tastytrade_mcp.utils.logging import get_logger

router = APIRouter(prefix="/positions", tags=["Positions"])
logger = get_logger(__name__)


# Response Models
class OptionsDetails(BaseModel):
    """Options-specific position details."""
    underlying_symbol: str
    strike_price: Decimal
    expiration_date: datetime
    option_type: str  # CALL or PUT
    contract_size: int = 100
    days_to_expiration: int
    in_the_money: bool
    intrinsic_value: Decimal
    extrinsic_value: Decimal
    greeks: Optional[Dict[str, float]] = None


class PositionDetails(BaseModel):
    """Position details response model."""
    symbol: str = Field(..., description="Position symbol")
    instrument_type: str = Field(..., description="EQUITY, OPTION, FUTURE, etc.")
    quantity: Decimal = Field(..., description="Position quantity")
    quantity_direction: str = Field(..., description="LONG or SHORT")

    # Cost basis
    average_open_price: Decimal = Field(..., description="Average cost per unit")
    cost_basis: Decimal = Field(..., description="Total cost basis")

    # Current values
    current_price: Optional[Decimal] = Field(None, description="Current market price")
    market_value: Decimal = Field(..., description="Current market value")

    # P&L calculations
    unrealized_pnl: Decimal = Field(..., description="Unrealized profit/loss")
    unrealized_pnl_percent: Decimal = Field(..., description="Unrealized P&L percentage")
    realized_pnl: Decimal = Field(Decimal(0), description="Realized profit/loss")
    daily_pnl: Optional[Decimal] = Field(None, description="Today's P&L")
    daily_pnl_percent: Optional[Decimal] = Field(None, description="Today's P&L percentage")

    # Options-specific
    options_details: Optional[OptionsDetails] = None

    # Metadata
    opened_at: Optional[datetime] = Field(None, description="Position open date")
    updated_at: datetime = Field(..., description="Last update time")

    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat() if v else None
        }


class PositionsResponse(BaseModel):
    """Response for get_positions endpoint."""
    account_number: str
    positions: List[PositionDetails]
    total_market_value: Decimal
    total_unrealized_pnl: Decimal
    total_realized_pnl: Decimal
    total_daily_pnl: Optional[Decimal]
    position_count: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat() if v else None
        }


@router.get("/{account_number}", response_model=PositionsResponse)
async def get_positions(
    account_number: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    instrument_type: Optional[str] = Query(None, description="Filter by instrument type"),
    sort_by: str = Query("market_value", description="Sort field (market_value, symbol, pnl)"),
) -> PositionsResponse:
    """
    Get all positions for a specific account.

    Fetches positions with real-time pricing and P&L calculations.
    """
    # Verify account ownership
    from tastytrade_mcp.api.accounts import get_account
    await get_account(account_number, current_user, session)

    # Get broker link
    broker_link = await get_active_broker_link(session, current_user)

    if not broker_link or broker_link.status != LinkStatus.ACTIVE:
        logger.warning(f"No active broker link found for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active TastyTrade account linked."
        )

    try:
        # Initialize TastyTrade service
        tastytrade = TastyTradeService(session)

        # Fetch positions
        logger.info(f"Fetching positions for account {account_number}")
        positions_data = await tastytrade.get_positions(broker_link, account_number)
        logger.info(f"Got {len(positions_data)} positions")

        # Extract unique symbols for batch pricing
        symbols = list(set(pos.get("symbol", "") for pos in positions_data if pos.get("symbol")))

        # Fetch real-time prices in parallel
        market_data = {}
        if symbols:
            try:
                quotes = await tastytrade.get_market_data(broker_link, symbols)
                market_data = {quote["symbol"]: quote for quote in quotes.get("items", [])}
            except Exception as e:
                logger.warning(f"Failed to fetch market data: {e}")

        # Process positions
        positions = []
        for pos in positions_data:
            position = await _process_position(pos, market_data)

            # Apply filter if specified
            if instrument_type and position.instrument_type != instrument_type:
                continue

            positions.append(position)

        # Sort positions
        if sort_by == "market_value":
            positions.sort(key=lambda p: abs(p.market_value), reverse=True)
        elif sort_by == "symbol":
            positions.sort(key=lambda p: p.symbol)
        elif sort_by == "pnl":
            positions.sort(key=lambda p: p.unrealized_pnl, reverse=True)

        # Calculate totals
        total_market_value = sum(p.market_value for p in positions)
        total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)
        total_realized_pnl = sum(p.realized_pnl for p in positions)
        total_daily_pnl = sum(p.daily_pnl for p in positions if p.daily_pnl)

        return PositionsResponse(
            account_number=account_number,
            positions=positions,
            total_market_value=total_market_value,
            total_unrealized_pnl=total_unrealized_pnl,
            total_realized_pnl=total_realized_pnl,
            total_daily_pnl=total_daily_pnl if total_daily_pnl else None,
            position_count=len(positions),
            timestamp=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch positions: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to fetch positions. Please try again later."
        )


async def _process_position(
    position_data: dict,
    market_data: dict
) -> PositionDetails:
    """Process raw position data into PositionDetails model."""
    symbol = position_data.get("symbol", "")
    instrument_type = position_data.get("instrument-type", "EQUITY")

    # Quantities and costs
    quantity = Decimal(str(position_data.get("quantity", 0)))
    quantity_direction = "LONG" if quantity > 0 else "SHORT"
    average_open_price = Decimal(str(position_data.get("average-open-price", 0)))

    # Calculate cost basis
    multiplier = Decimal(str(position_data.get("multiplier", 1)))
    cost_basis = abs(quantity) * average_open_price * multiplier

    # Get current price from market data
    quote = market_data.get(symbol, {})
    current_price = None
    daily_pnl = None
    daily_pnl_percent = None

    if quote:
        # Use mid price for current value
        bid = Decimal(str(quote.get("bid", 0)))
        ask = Decimal(str(quote.get("ask", 0)))
        current_price = (bid + ask) / 2 if bid and ask else bid or ask

        # Daily P&L from previous close
        prev_close = Decimal(str(quote.get("previous-close", 0)))
        if prev_close and current_price:
            daily_pnl = (current_price - prev_close) * quantity * multiplier
            if prev_close > 0:
                daily_pnl_percent = ((current_price - prev_close) / prev_close) * 100

    # Use mark price if no quote available
    if not current_price:
        current_price = Decimal(str(position_data.get("mark", 0)))

    # Calculate market value and P&L
    market_value = quantity * current_price * multiplier
    unrealized_pnl = market_value - (quantity * average_open_price * multiplier)
    unrealized_pnl_percent = (unrealized_pnl / cost_basis * 100) if cost_basis else Decimal(0)

    # Get realized P&L
    realized_pnl = Decimal(str(position_data.get("realized-gain-loss", 0)))

    # Parse options details if applicable
    options_details = None
    if instrument_type == "EQUITY_OPTION":
        options_details = _parse_options_details(position_data, current_price)

    return PositionDetails(
        symbol=symbol,
        instrument_type=instrument_type,
        quantity=quantity,
        quantity_direction=quantity_direction,
        average_open_price=average_open_price,
        cost_basis=cost_basis,
        current_price=current_price,
        market_value=market_value,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_percent=unrealized_pnl_percent,
        realized_pnl=realized_pnl,
        daily_pnl=daily_pnl,
        daily_pnl_percent=daily_pnl_percent,
        options_details=options_details,
        opened_at=_parse_date(position_data.get("created-at")),
        updated_at=datetime.utcnow()
    )


def _parse_options_details(position_data: dict, current_price: Decimal) -> Optional[OptionsDetails]:
    """Parse options-specific details from position data."""
    try:
        # Parse options symbol (e.g., "AAPL 230120C00150000")
        symbol = position_data.get("symbol", "")
        underlying = position_data.get("underlying-symbol", "")

        # Extract from position data
        strike = Decimal(str(position_data.get("strike-price", 0)))
        expiration = _parse_date(position_data.get("expires-at"))
        option_type = position_data.get("option-type", "")  # CALL or PUT

        if not expiration:
            return None

        # Calculate days to expiration
        # Make expiration timezone-naive if it has timezone info
        if expiration.tzinfo is not None:
            expiration_naive = expiration.replace(tzinfo=None)
        else:
            expiration_naive = expiration
        days_to_exp = (expiration_naive - datetime.utcnow()).days

        # Calculate intrinsic and extrinsic value
        underlying_price = Decimal(str(position_data.get("underlying-price", 0)))
        intrinsic_value = Decimal(0)

        if option_type == "CALL":
            intrinsic_value = max(underlying_price - strike, Decimal(0))
        elif option_type == "PUT":
            intrinsic_value = max(strike - underlying_price, Decimal(0))

        extrinsic_value = current_price - intrinsic_value if current_price else Decimal(0)
        in_the_money = intrinsic_value > 0

        # Get Greeks if available
        greeks = None
        if position_data.get("delta"):
            greeks = {
                "delta": float(position_data.get("delta", 0)),
                "gamma": float(position_data.get("gamma", 0)),
                "theta": float(position_data.get("theta", 0)),
                "vega": float(position_data.get("vega", 0)),
                "rho": float(position_data.get("rho", 0))
            }

        return OptionsDetails(
            underlying_symbol=underlying,
            strike_price=strike,
            expiration_date=expiration,
            option_type=option_type,
            days_to_expiration=days_to_exp,
            in_the_money=in_the_money,
            intrinsic_value=intrinsic_value,
            extrinsic_value=extrinsic_value,
            greeks=greeks
        )
    except Exception as e:
        logger.warning(f"Failed to parse options details: {e}")
        return None


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO date string to datetime."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


@router.get("/{account_number}/summary")
async def get_positions_summary(
    account_number: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get summary statistics for account positions."""
    positions_response = await get_positions(account_number, current_user, session)

    # Calculate summary stats
    long_positions = [p for p in positions_response.positions if p.quantity > 0]
    short_positions = [p for p in positions_response.positions if p.quantity < 0]

    winners = [p for p in positions_response.positions if p.unrealized_pnl > 0]
    losers = [p for p in positions_response.positions if p.unrealized_pnl < 0]

    return {
        "account_number": account_number,
        "total_positions": positions_response.position_count,
        "long_positions": len(long_positions),
        "short_positions": len(short_positions),
        "total_market_value": float(positions_response.total_market_value),
        "total_unrealized_pnl": float(positions_response.total_unrealized_pnl),
        "total_realized_pnl": float(positions_response.total_realized_pnl),
        "winning_positions": len(winners),
        "losing_positions": len(losers),
        "win_rate": (len(winners) / positions_response.position_count * 100)
                    if positions_response.position_count else 0,
        "largest_winner": max((p.unrealized_pnl for p in winners), default=0),
        "largest_loser": min((p.unrealized_pnl for p in losers), default=0),
        "timestamp": positions_response.timestamp.isoformat()
    }