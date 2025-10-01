"""Balance and account metrics API endpoints."""
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from tastytrade_mcp.api.auth import get_current_user
from tastytrade_mcp.api.helpers import get_active_broker_link
from tastytrade_mcp.db.session import get_session
from tastytrade_mcp.models.auth import BrokerLink, LinkStatus
from tastytrade_mcp.models.user import User
from tastytrade_mcp.services.tastytrade import TastyTradeService
from tastytrade_mcp.utils.logging import get_logger

router = APIRouter(prefix="/balances", tags=["Balances"])
logger = get_logger(__name__)


# Response Models
class CashDetails(BaseModel):
    """Detailed cash breakdown."""
    settled_cash: Decimal = Field(..., description="Settled cash available")
    unsettled_cash: Decimal = Field(..., description="Unsettled cash from recent trades")
    pending_cash: Decimal = Field(..., description="Pending cash from orders")
    total_cash: Decimal = Field(..., description="Total cash (settled + unsettled)")
    cash_available_to_trade: Decimal = Field(..., description="Cash available for trading")
    cash_available_to_withdraw: Decimal = Field(..., description="Cash available for withdrawal")


class MarginDetails(BaseModel):
    """Margin account specific details."""
    margin_buying_power: Decimal = Field(..., description="Margin buying power")
    stock_buying_power: Decimal = Field(..., description="Stock buying power")
    option_buying_power: Decimal = Field(..., description="Option buying power")
    day_trading_buying_power: Optional[Decimal] = Field(None, description="Day trading buying power (PDT accounts)")
    maintenance_requirement: Decimal = Field(..., description="Maintenance margin requirement")
    maintenance_excess: Decimal = Field(..., description="Excess above maintenance requirement")
    initial_requirement: Decimal = Field(..., description="Initial margin requirement")
    fed_call: Decimal = Field(Decimal(0), description="Federal call amount")
    maintenance_call: Decimal = Field(Decimal(0), description="Maintenance call amount")


class RiskMetrics(BaseModel):
    """Account risk metrics."""
    margin_utilization_percent: Decimal = Field(..., description="Percentage of margin used")
    risk_level: str = Field(..., description="LOW, MEDIUM, HIGH, CRITICAL")
    buying_power_effect: Decimal = Field(..., description="Effect on buying power from positions")
    portfolio_volatility: Optional[Decimal] = Field(None, description="Portfolio volatility estimate")
    is_pattern_day_trader: bool = Field(False, description="PDT status")
    is_in_margin_call: bool = Field(False, description="Whether account is in margin call")
    days_until_fed_call: Optional[int] = Field(None, description="Days until federal call due")


class BalanceDetails(BaseModel):
    """Comprehensive balance information."""
    account_number: str = Field(..., description="Account identifier")
    account_type: str = Field(..., description="CASH or MARGIN")

    # Core balances
    net_liquidating_value: Decimal = Field(..., description="Total account value (NLV)")
    equity_value: Decimal = Field(..., description="Total equity value")
    total_market_value: Decimal = Field(..., description="Total market value of positions")

    # Cash details
    cash_details: CashDetails

    # Margin details (if applicable)
    margin_details: Optional[MarginDetails] = None

    # Risk metrics
    risk_metrics: RiskMetrics

    # P&L
    daily_pnl: Optional[Decimal] = Field(None, description="Today's P&L")
    daily_pnl_percent: Optional[Decimal] = Field(None, description="Today's P&L percentage")

    # Timestamps
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    market_session: str = Field(..., description="REGULAR, PRE_MARKET, AFTER_HOURS, CLOSED")

    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat() if v else None
        }


@router.get("/{account_number}", response_model=BalanceDetails)
async def get_balances(
    account_number: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    include_positions: bool = True,
) -> BalanceDetails:
    """
    Get comprehensive balance information for an account.

    Includes cash, margin, and risk metrics with real-time NLV calculation.
    """
    # Verify account ownership
    from tastytrade_mcp.api.accounts import get_account
    account = await get_account(account_number, current_user, session)

    # Get broker link
    broker_link = await get_active_broker_link(session, current_user)

    if not broker_link or broker_link.status != LinkStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active TastyTrade account linked."
        )

    try:
        # Initialize TastyTrade service
        tastytrade = TastyTradeService(session)

        # Fetch balance data
        balance_data = await tastytrade.get_balances(broker_link, account_number)

        # Determine account type
        account_type = account.margin_or_cash if hasattr(account, 'margin_or_cash') else "CASH"
        is_margin = account_type == "MARGIN"

        # Parse cash details
        cash_details = _parse_cash_details(balance_data)

        # Parse margin details if applicable
        margin_details = None
        if is_margin:
            margin_details = _parse_margin_details(balance_data)

        # Calculate real-time NLV if positions included
        positions_value = Decimal(str(balance_data.get("equity-value", 0)))
        if include_positions:
            # Get positions for real-time market value
            from tastytrade_mcp.api.positions import get_positions
            positions_response = await get_positions(
                account_number, current_user, session
            )
            positions_value = positions_response.total_market_value

        # Calculate NLV
        nlv = cash_details.total_cash + positions_value

        # Calculate daily P&L
        daily_pnl = None
        daily_pnl_percent = None
        if balance_data.get("day-change"):
            daily_pnl = Decimal(str(balance_data["day-change"]))
            if nlv > 0:
                daily_pnl_percent = (daily_pnl / nlv) * 100

        # Calculate risk metrics
        risk_metrics = _calculate_risk_metrics(
            balance_data, nlv, is_margin, margin_details
        )

        # Determine market session
        market_session = _determine_market_session()

        return BalanceDetails(
            account_number=account_number,
            account_type=account_type,
            net_liquidating_value=nlv,
            equity_value=positions_value,
            total_market_value=positions_value,
            cash_details=cash_details,
            margin_details=margin_details,
            risk_metrics=risk_metrics,
            daily_pnl=daily_pnl,
            daily_pnl_percent=daily_pnl_percent,
            market_session=market_session,
            updated_at=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch balances: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to fetch balance information. Please try again later."
        )


def _parse_cash_details(balance_data: dict) -> CashDetails:
    """Parse cash details from balance data."""
    settled_cash = Decimal(str(balance_data.get("cash-balance", 0)))
    unsettled_cash = Decimal(str(balance_data.get("unsettled-funds", 0)))
    pending_cash = Decimal(str(balance_data.get("pending-cash", 0)))

    total_cash = settled_cash + unsettled_cash

    # Available to trade includes unsettled for some operations
    cash_available_to_trade = Decimal(str(
        balance_data.get("cash-available-for-trading", settled_cash)
    ))

    # Only settled cash can be withdrawn
    cash_available_to_withdraw = Decimal(str(
        balance_data.get("cash-available-for-withdrawal", settled_cash)
    ))

    return CashDetails(
        settled_cash=settled_cash,
        unsettled_cash=unsettled_cash,
        pending_cash=pending_cash,
        total_cash=total_cash,
        cash_available_to_trade=cash_available_to_trade,
        cash_available_to_withdraw=cash_available_to_withdraw
    )


def _parse_margin_details(balance_data: dict) -> MarginDetails:
    """Parse margin account details from balance data."""
    return MarginDetails(
        margin_buying_power=Decimal(str(
            balance_data.get("margin-buying-power", 0)
        )),
        stock_buying_power=Decimal(str(
            balance_data.get("stock-buying-power", 0)
        )),
        option_buying_power=Decimal(str(
            balance_data.get("option-buying-power", 0)
        )),
        day_trading_buying_power=Decimal(str(
            balance_data.get("day-trading-buying-power", 0)
        )) if balance_data.get("day-trading-buying-power") else None,
        maintenance_requirement=Decimal(str(
            balance_data.get("maintenance-requirement", 0)
        )),
        maintenance_excess=Decimal(str(
            balance_data.get("maintenance-excess", 0)
        )),
        initial_requirement=Decimal(str(
            balance_data.get("initial-requirement", 0)
        )),
        fed_call=Decimal(str(balance_data.get("fed-call", 0))),
        maintenance_call=Decimal(str(balance_data.get("maintenance-call", 0)))
    )


def _calculate_risk_metrics(
    balance_data: dict,
    nlv: Decimal,
    is_margin: bool,
    margin_details: Optional[MarginDetails]
) -> RiskMetrics:
    """Calculate risk metrics for the account."""
    # Default values for cash accounts
    margin_utilization = Decimal(0)
    risk_level = "LOW"
    buying_power_effect = Decimal(0)
    is_in_margin_call = False

    if is_margin and margin_details and nlv > 0:
        # Calculate margin utilization
        if margin_details.maintenance_requirement > 0:
            margin_utilization = (
                margin_details.maintenance_requirement / nlv
            ) * 100

        # Calculate buying power effect
        buying_power_effect = margin_details.maintenance_requirement

        # Determine risk level
        if margin_utilization >= 90:
            risk_level = "CRITICAL"
        elif margin_utilization >= 75:
            risk_level = "HIGH"
        elif margin_utilization >= 50:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        # Check for margin calls
        is_in_margin_call = (
            margin_details.fed_call > 0 or
            margin_details.maintenance_call > 0
        )

    # Check PDT status
    is_pdt = balance_data.get("pattern-day-trader", False)

    return RiskMetrics(
        margin_utilization_percent=margin_utilization,
        risk_level=risk_level,
        buying_power_effect=buying_power_effect,
        portfolio_volatility=None,  # Would need position-level data
        is_pattern_day_trader=is_pdt,
        is_in_margin_call=is_in_margin_call,
        days_until_fed_call=None  # Would need call date info
    )


def _determine_market_session() -> str:
    """Determine current market session."""
    import pytz
    from tastytrade_mcp.config.settings import get_settings

    settings = get_settings()

    # Get current time in market timezone
    market_tz = pytz.timezone(settings.market_timezone)
    now_market = datetime.now(market_tz)
    current_time = now_market.time()
    weekday = now_market.weekday()

    # Market closed on weekends
    if weekday >= 5:  # Saturday = 5, Sunday = 6
        return "CLOSED"

    # Use market hours from settings
    if current_time < settings.market_pre_open_time:
        return "CLOSED"
    elif current_time < settings.market_open_time:
        return "PRE_MARKET"
    elif current_time < settings.market_close_time:
        return "REGULAR"
    elif current_time < settings.market_after_hours_close_time:
        return "AFTER_HOURS"
    else:
        return "CLOSED"


@router.get("/{account_number}/buying-power")
async def get_buying_power(
    account_number: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Get simplified buying power information.

    Quick endpoint for checking available trading power.
    """
    balances = await get_balances(account_number, current_user, session, include_positions=False)

    response = {
        "account_number": account_number,
        "account_type": balances.account_type,
        "cash_available": float(balances.cash_details.cash_available_to_trade),
        "net_liquidating_value": float(balances.net_liquidating_value),
        "risk_level": balances.risk_metrics.risk_level,
        "is_in_margin_call": balances.risk_metrics.is_in_margin_call,
        "timestamp": balances.updated_at.isoformat()
    }

    if balances.margin_details:
        response.update({
            "stock_buying_power": float(balances.margin_details.stock_buying_power),
            "option_buying_power": float(balances.margin_details.option_buying_power),
            "margin_buying_power": float(balances.margin_details.margin_buying_power),
            "day_trading_buying_power": float(balances.margin_details.day_trading_buying_power)
                if balances.margin_details.day_trading_buying_power else None,
        })

    return response


@router.get("/{account_number}/margin-requirements")
async def get_margin_requirements(
    account_number: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Get margin requirement details for margin accounts.

    Returns error for cash accounts.
    """
    balances = await get_balances(account_number, current_user, session, include_positions=False)

    if balances.account_type != "MARGIN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Margin requirements only available for margin accounts"
        )

    if not balances.margin_details:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve margin details"
        )

    return {
        "account_number": account_number,
        "maintenance_requirement": float(balances.margin_details.maintenance_requirement),
        "maintenance_excess": float(balances.margin_details.maintenance_excess),
        "initial_requirement": float(balances.margin_details.initial_requirement),
        "margin_utilization_percent": float(balances.risk_metrics.margin_utilization_percent),
        "fed_call": float(balances.margin_details.fed_call),
        "maintenance_call": float(balances.margin_details.maintenance_call),
        "is_in_margin_call": balances.risk_metrics.is_in_margin_call,
        "risk_level": balances.risk_metrics.risk_level,
        "timestamp": balances.updated_at.isoformat()
    }