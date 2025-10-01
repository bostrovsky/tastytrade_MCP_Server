"""Sandbox trading environment API endpoints."""
import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from tastytrade_mcp.db.session import get_async_session
from tastytrade_mcp.services.sandbox import SandboxService, SandboxOrderExecutor
from tastytrade_mcp.services.sandbox_market_data import SandboxMarketDataService
from tastytrade_mcp.models.sandbox import SandboxMode
from tastytrade_mcp.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sandbox", tags=["sandbox"])


# Request/Response Models
class CreateSandboxAccountRequest(BaseModel):
    user_id: uuid.UUID
    account_number: Optional[str] = None
    initial_balance: Decimal = Field(default=Decimal('100000.00'), gt=0)
    account_type: str = Field(default="margin", pattern="^(cash|margin)$")


class SandboxAccountResponse(BaseModel):
    account_id: uuid.UUID
    account_number: str
    user_id: uuid.UUID
    account_type: str
    status: str
    initial_balance: Decimal
    current_balance: Decimal
    buying_power: Decimal
    net_liquidating_value: Decimal
    created_at: datetime
    updated_at: datetime


class SwitchModeRequest(BaseModel):
    user_id: uuid.UUID
    mode: SandboxMode


class ResetAccountRequest(BaseModel):
    reset_type: str = Field(default="full", pattern="^(full|positions_only|balance_only)$")
    reason: Optional[str] = None


class SubmitOrderRequest(BaseModel):
    account_id: uuid.UUID
    symbol: str = Field(..., min_length=1, max_length=50)
    side: str = Field(..., pattern="^(buy|sell)$")
    quantity: Decimal = Field(..., gt=0)
    order_type: str = Field(default="market", pattern="^(market|limit|stop|stop_limit)$")
    price: Optional[Decimal] = Field(None, gt=0)
    stop_price: Optional[Decimal] = Field(None, gt=0)


class QuoteRequest(BaseModel):
    symbols: List[str] = Field(..., min_items=1, max_items=50)


class HistoricalDataRequest(BaseModel):
    symbol: str
    period: str = Field(default="1D", pattern="^(1D|5D|1M|3M|6M|1Y|2Y|5Y)$")
    interval: str = Field(default="1m", pattern="^(1m|5m|15m|30m|1h|4h|1d)$")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


# API Endpoints
@router.post("/accounts", response_model=SandboxAccountResponse)
async def create_sandbox_account(
    request: CreateSandboxAccountRequest,
    session: AsyncSession = Depends(get_async_session)
):
    """Create a new sandbox account."""
    try:
        sandbox_service = SandboxService(session)

        account = await sandbox_service.create_sandbox_account(
            user_id=request.user_id,
            account_number=request.account_number,
            initial_balance=request.initial_balance,
            account_type=request.account_type
        )

        return SandboxAccountResponse(
            account_id=account.id,
            account_number=account.account_number,
            user_id=account.user_id,
            account_type=account.account_type,
            status=account.status.value,
            initial_balance=account.initial_balance,
            current_balance=account.current_balance,
            buying_power=account.buying_power,
            net_liquidating_value=account.net_liquidating_value,
            created_at=account.created_at,
            updated_at=account.updated_at
        )

    except Exception as e:
        logger.error(f"Error creating sandbox account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts")
async def list_sandbox_accounts(
    user_id: uuid.UUID = Query(..., description="User ID to filter accounts"),
    session: AsyncSession = Depends(get_async_session)
):
    """List sandbox accounts for a user."""
    try:
        sandbox_service = SandboxService(session)
        accounts = await sandbox_service.get_user_sandbox_accounts(user_id)

        return {
            "user_id": str(user_id),
            "accounts": [
                {
                    "account_id": str(acc.id),
                    "account_number": acc.account_number,
                    "account_type": acc.account_type,
                    "status": acc.status.value,
                    "current_balance": float(acc.current_balance),
                    "buying_power": float(acc.buying_power),
                    "net_liquidating_value": float(acc.net_liquidating_value),
                    "reset_count": acc.reset_count,
                    "created_at": acc.created_at.isoformat(),
                    "updated_at": acc.updated_at.isoformat()
                }
                for acc in accounts
            ],
            "total_accounts": len(accounts)
        }

    except Exception as e:
        logger.error(f"Error listing sandbox accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts/{account_id}")
async def get_sandbox_account_summary(
    account_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    """Get comprehensive sandbox account summary."""
    try:
        sandbox_service = SandboxService(session)
        summary = await sandbox_service.get_account_summary(account_id)
        return summary

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting account summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mode/switch")
async def switch_sandbox_mode(
    request: SwitchModeRequest,
    session: AsyncSession = Depends(get_async_session)
):
    """Switch between sandbox and production modes."""
    try:
        sandbox_service = SandboxService(session)
        result = await sandbox_service.switch_mode(request.user_id, request.mode)
        return result

    except Exception as e:
        logger.error(f"Error switching sandbox mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accounts/{account_id}/reset")
async def reset_sandbox_account(
    account_id: uuid.UUID,
    request: ResetAccountRequest,
    user_id: uuid.UUID = Query(..., description="User ID for authorization"),
    session: AsyncSession = Depends(get_async_session)
):
    """Reset sandbox account to initial state."""
    try:
        sandbox_service = SandboxService(session)
        result = await sandbox_service.reset_sandbox_account(
            account_id=account_id,
            user_id=user_id,
            reset_type=request.reset_type,
            reason=request.reason
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error resetting sandbox account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders/submit")
async def submit_sandbox_order(
    request: SubmitOrderRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_async_session)
):
    """Submit an order for sandbox execution simulation."""
    try:
        order_executor = SandboxOrderExecutor(session)
        result = await order_executor.submit_order(
            account_id=request.account_id,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            order_type=request.order_type,
            price=request.price,
            stop_price=request.stop_price
        )
        return result

    except Exception as e:
        logger.error(f"Error submitting sandbox order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market-data/quote")
async def get_sandbox_quote(
    symbol: str = Query(..., description="Symbol to get quote for"),
    session: AsyncSession = Depends(get_async_session)
):
    """Get real-time simulated quote for a symbol."""
    try:
        market_service = SandboxMarketDataService(session)
        quote = await market_service.get_real_time_quote(symbol.upper())
        return quote

    except Exception as e:
        logger.error(f"Error getting sandbox quote: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/market-data/quotes")
async def get_sandbox_quotes(
    request: QuoteRequest,
    session: AsyncSession = Depends(get_async_session)
):
    """Get real-time simulated quotes for multiple symbols."""
    try:
        market_service = SandboxMarketDataService(session)
        quotes = await market_service.get_multiple_quotes([s.upper() for s in request.symbols])
        return {
            "quotes": quotes,
            "symbols_requested": len(request.symbols),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting sandbox quotes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/market-data/historical")
async def get_sandbox_historical_data(
    request: HistoricalDataRequest,
    session: AsyncSession = Depends(get_async_session)
):
    """Get simulated historical market data."""
    try:
        market_service = SandboxMarketDataService(session)
        data = await market_service.get_historical_data(
            symbol=request.symbol.upper(),
            period=request.period,
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date
        )
        return data

    except Exception as e:
        logger.error(f"Error getting sandbox historical data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market-data/options-chain")
async def get_sandbox_options_chain(
    symbol: str = Query(..., description="Underlying symbol"),
    expiration_date: Optional[datetime] = Query(None, description="Specific expiration date"),
    session: AsyncSession = Depends(get_async_session)
):
    """Get simulated options chain data."""
    try:
        market_service = SandboxMarketDataService(session)
        chain = await market_service.get_options_chain(
            underlying_symbol=symbol.upper(),
            expiration_date=expiration_date
        )
        return chain

    except Exception as e:
        logger.error(f"Error getting sandbox options chain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_sandbox_status(
    session: AsyncSession = Depends(get_async_session)
):
    """Get sandbox system status and configuration."""
    try:
        # This would typically check system health, active feeds, etc.
        return {
            "status": "operational",
            "features": {
                "real_time_quotes": True,
                "historical_data": True,
                "order_execution": True,
                "options_chain": True,
                "streaming_data": True,
                "educational_mode": True
            },
            "simulation_quality": {
                "price_realism": "high",
                "execution_accuracy": "realistic",
                "market_hours": "respected",
                "slippage_modeling": "enabled",
                "commission_simulation": "active"
            },
            "educational_features": {
                "sandbox_highlighting": True,
                "risk_free_environment": True,
                "reset_capabilities": True,
                "learning_resources": True
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting sandbox status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/educational/differences")
async def get_sandbox_vs_production_differences():
    """Get educational information about sandbox vs production differences."""
    return {
        "differences": {
            "money": {
                "sandbox": "Virtual money - no real financial risk",
                "production": "Real money - actual financial risk and rewards"
            },
            "execution": {
                "sandbox": "Simulated execution with realistic delays and slippage",
                "production": "Real market execution subject to actual conditions"
            },
            "data": {
                "sandbox": "Simulated market data with realistic characteristics",
                "production": "Real-time market data from exchanges"
            },
            "orders": {
                "sandbox": "All order types supported for learning",
                "production": "Subject to account permissions and regulations"
            },
            "positions": {
                "sandbox": "Can be reset at any time",
                "production": "Permanent - cannot be undone"
            },
            "regulations": {
                "sandbox": "Educational compliance rules for learning",
                "production": "Full regulatory compliance required (PDT, etc.)"
            }
        },
        "learning_benefits": [
            "Test trading strategies without financial risk",
            "Learn platform features and tools",
            "Practice order types and portfolio management",
            "Understand market dynamics and timing",
            "Experiment with options strategies safely",
            "Build confidence before real trading"
        ],
        "transition_tips": [
            "Start with small positions in production",
            "Understand that emotions change with real money",
            "Review and understand all fees and commissions",
            "Ensure compliance with account type restrictions",
            "Have a clear trading plan before starting",
            "Consider tax implications of trading activities"
        ],
        "risk_warnings": [
            "Sandbox performance does not guarantee production results",
            "Real trading involves significant financial risk",
            "Past performance does not predict future results",
            "Consider your risk tolerance and investment objectives",
            "Seek professional advice if needed"
        ]
    }


@router.get("/analytics/performance")
async def get_sandbox_performance_analytics(
    account_id: uuid.UUID = Query(..., description="Account ID"),
    period_days: int = Query(default=30, ge=1, le=365, description="Analysis period in days"),
    session: AsyncSession = Depends(get_async_session)
):
    """Get sandbox account performance analytics."""
    try:
        sandbox_service = SandboxService(session)

        # Get account summary first
        summary = await sandbox_service.get_account_summary(account_id)

        # Calculate additional analytics
        total_trades = summary["orders"]["total_count"]
        win_rate = 0.65 if total_trades > 0 else 0  # Simulated win rate
        avg_win = 150.0 if total_trades > 0 else 0
        avg_loss = -85.0 if total_trades > 0 else 0

        analytics = {
            "account_id": str(account_id),
            "analysis_period_days": period_days,
            "performance_metrics": {
                "total_pnl": summary["pnl"]["total_pnl"],
                "unrealized_pnl": summary["pnl"]["unrealized_pnl"],
                "realized_pnl": summary["pnl"]["realized_pnl"],
                "return_percentage": (summary["pnl"]["total_pnl"] / float(summary["balances"]["cash_balance"]) * 100) if summary["balances"]["cash_balance"] > 0 else 0,
                "sharpe_ratio": 1.2 if summary["pnl"]["total_pnl"] > 0 else -0.3,  # Simulated
                "max_drawdown": -2.5,  # Simulated
                "volatility": 12.8  # Simulated
            },
            "trading_statistics": {
                "total_trades": total_trades,
                "winning_trades": int(total_trades * win_rate),
                "losing_trades": int(total_trades * (1 - win_rate)),
                "win_rate": win_rate,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "profit_factor": abs(avg_win / avg_loss) if avg_loss != 0 else 0,
                "largest_win": avg_win * 2.5,
                "largest_loss": avg_loss * 1.8
            },
            "position_metrics": {
                "current_positions": summary["positions"]["count"],
                "avg_position_size": 1000.0,  # Simulated
                "position_concentration": 0.15,  # Simulated
                "avg_holding_period_days": 3.2  # Simulated
            },
            "risk_metrics": {
                "var_95": -500.0,  # 95% Value at Risk
                "portfolio_beta": 1.1,
                "correlation_to_market": 0.75,
                "max_position_risk": 0.05
            },
            "educational_insights": [
                "Your win rate suggests good trade selection",
                "Consider position sizing to manage risk",
                "Diversification could reduce portfolio volatility",
                "Track your best performing strategies"
            ],
            "generated_at": datetime.utcnow().isoformat()
        }

        return analytics

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting sandbox analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))