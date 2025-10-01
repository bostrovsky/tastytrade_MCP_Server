"""Account management API endpoints."""
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from tastytrade_mcp.api.auth import get_current_user
from tastytrade_mcp.api.helpers import get_active_broker_link
from tastytrade_mcp.db.session import get_session
from tastytrade_mcp.models.auth import BrokerLink, LinkStatus
from tastytrade_mcp.models.user import User
from tastytrade_mcp.services.cache import get_cache
from tastytrade_mcp.services.tastytrade import TastyTradeService
from tastytrade_mcp.utils.logging import get_logger

router = APIRouter(prefix="/accounts", tags=["Accounts"])
logger = get_logger(__name__)


# Response Models
class AccountDetails(BaseModel):
    """Account details response model."""
    account_number: str = Field(..., description="Account identifier")
    nickname: Optional[str] = Field(None, description="User-defined nickname")
    account_type: str = Field(..., description="Account type (e.g., MARGIN, CASH)")
    status: str = Field(..., description="Account status (e.g., ACTIVE, CLOSED)")
    opening_date: Optional[datetime] = Field(None, description="Account opening date")
    approval_levels: List[str] = Field(default_factory=list, description="Trading approval levels")
    is_firm_error: bool = Field(False, description="Whether account has firm errors")
    is_test_drive: bool = Field(False, description="Whether this is a test account")
    margin_or_cash: str = Field(..., description="MARGIN or CASH")
    is_foreign: bool = Field(False, description="Whether account is foreign")
    funding_date: Optional[datetime] = Field(None, description="Initial funding date")

    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class AccountsResponse(BaseModel):
    """Response for get_accounts endpoint."""
    accounts: List[AccountDetails]
    cached: bool = Field(False, description="Whether response was served from cache")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


@router.get("/", response_model=AccountsResponse)
async def get_accounts(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AccountsResponse:
    """
    Get all linked TastyTrade accounts for the authenticated user.

    Fetches account details using OAuth tokens with 5-minute caching.
    """
    # Check cache first
    cache = await get_cache()
    cache_key = f"accounts:{current_user.id}"

    if cache:
        cached_data = await cache.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached accounts for user {current_user.id}")
            return AccountsResponse(
                accounts=cached_data["accounts"],
                cached=True,
                timestamp=cached_data["timestamp"]
            )

    # Get broker link
    broker_link = await get_active_broker_link(session, current_user)

    if not broker_link or broker_link.status != LinkStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active TastyTrade account linked. Please complete OAuth flow first."
        )

    try:
        # Initialize TastyTrade service
        tastytrade = TastyTradeService(session)

        # Get accounts using OAuth tokens
        accounts_data = await tastytrade.get_accounts(broker_link)

        # Transform to response model with PII scrubbing
        accounts = []
        for account in accounts_data:
            # Scrub PII - remove SSN, full legal name, etc.
            accounts.append(AccountDetails(
                account_number=account.get("account-number", ""),
                nickname=account.get("nickname"),
                account_type=account.get("account-type-name", "UNKNOWN"),
                status="ACTIVE" if not account.get("is-closed", False) else "CLOSED",
                opening_date=_parse_date(account.get("opened-at")),
                approval_levels=_parse_approval_levels(account),
                is_firm_error=account.get("is-firm-error", False),
                is_test_drive=account.get("is-test-drive", False),
                margin_or_cash=account.get("margin-or-cash", "CASH"),
                is_foreign=account.get("is-foreign", False),
                funding_date=_parse_date(account.get("funded-at")),
            ))

        response_data = {
            "accounts": accounts,
            "timestamp": datetime.utcnow()
        }

        # Cache for 5 minutes
        if cache:
            await cache.set(cache_key, response_data, ttl=300)
            logger.info(f"Cached {len(accounts)} accounts for user {current_user.id}")

        return AccountsResponse(
            accounts=accounts,
            cached=False,
            timestamp=response_data["timestamp"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch accounts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to fetch accounts. Please try again later."
        )


@router.get("/{account_number}", response_model=AccountDetails)
async def get_account(
    account_number: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AccountDetails:
    """
    Get details for a specific account.

    Verifies user owns the account before returning details.
    """
    # Get all accounts
    accounts_response = await get_accounts(current_user, session)

    # Find requested account
    for account in accounts_response.accounts:
        if account.account_number == account_number:
            return account

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Account {account_number} not found or not authorized"
    )


@router.post("/{account_number}/refresh")
async def refresh_account_cache(
    account_number: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Force refresh of account cache.

    Clears cache and fetches fresh data from TastyTrade.
    """
    # Verify account ownership
    await get_account(account_number, current_user, session)

    # Clear cache
    cache = await get_cache()
    if cache:
        cache_key = f"accounts:{current_user.id}"
        await cache.delete(cache_key)
        logger.info(f"Cleared account cache for user {current_user.id}")

    # Fetch fresh data
    await get_accounts(current_user, session)

    return {"message": "Account cache refreshed successfully"}


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO date string to datetime."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _parse_approval_levels(account: dict) -> List[str]:
    """Extract approval levels from account data."""
    levels = []

    # Options approval
    if account.get("suitable-options-level"):
        levels.append(f"Options Level {account['suitable-options-level']}")

    # Futures approval
    if account.get("futures-account-purpose"):
        levels.append("Futures")

    # Crypto approval
    if account.get("cryptocurrency-account-purpose"):
        levels.append("Cryptocurrency")

    # Day trading
    if account.get("day-trader-status"):
        levels.append("Pattern Day Trader")

    return levels