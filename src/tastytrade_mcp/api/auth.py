"""Authentication API endpoints."""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tastytrade_mcp.auth.jwt_service import get_jwt_service
from tastytrade_mcp.auth.oauth_service import OAuthService
from tastytrade_mcp.db.session import get_session
from tastytrade_mcp.models.auth import BrokerLink, LinkStatus
from tastytrade_mcp.models.user import User, UserStatus
from tastytrade_mcp.utils.logging import get_logger

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger(__name__)
security = HTTPBearer()


# Request/Response Models
class OAuthInitiateRequest(BaseModel):
    """Request to initiate OAuth flow."""
    user_id: Optional[UUID] = None  # If None, create new user
    is_sandbox: bool = True
    redirect_uri: Optional[str] = None


class OAuthInitiateResponse(BaseModel):
    """Response with OAuth authorization URL."""
    auth_url: str
    state: str
    expires_at: datetime
    user_id: UUID


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class AuthStatusResponse(BaseModel):
    """Authentication status response."""
    authenticated: bool
    user_id: Optional[UUID] = None
    broker_linked: bool = False
    subscription_active: bool = False
    is_sandbox: bool = True
    accounts: list[str] = []


class RefreshTokenRequest(BaseModel):
    """Request to refresh access token."""
    refresh_token: str


# Dependency to get current user from JWT
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> User:
    """
    Get current user from JWT token.
    
    Args:
        credentials: Bearer token from Authorization header
        session: Database session
    
    Returns:
        Current user
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    jwt_service = get_jwt_service()
    
    # Verify token
    token_data = jwt_service.verify_token(credentials.credentials)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    result = await session.execute(
        select(User).where(User.id == UUID(token_data.sub))
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active",
        )
    
    return user


from fastapi import Header

# Optional dependency to get current user if authenticated
async def get_optional_user(
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session),
) -> Optional[User]:
    """Get current user if authenticated, None otherwise."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    token = authorization.replace("Bearer ", "")
    jwt_service = get_jwt_service()
    
    # Verify token
    token_data = jwt_service.verify_token(token)
    if not token_data:
        return None
    
    # Get user from database
    result = await session.execute(
        select(User).where(User.id == UUID(token_data.sub))
    )
    user = result.scalar_one_or_none()
    
    if not user or user.status != UserStatus.ACTIVE:
        return None
    
    return user


@router.post("/oauth/initiate", response_model=OAuthInitiateResponse)
async def initiate_oauth(
    request: OAuthInitiateRequest,
    session: AsyncSession = Depends(get_session),
) -> OAuthInitiateResponse:
    """
    Initiate OAuth flow with TastyTrade.
    
    Creates or uses existing user and returns authorization URL.
    """
    # Get or create user
    if request.user_id:
        # Convert to UUID if it's a string
        user_id = request.user_id if isinstance(request.user_id, UUID) else UUID(str(request.user_id))
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
    else:
        # Create new user with temporary email
        user = User(
            id=uuid4(),
            email=f"temp_{uuid4().hex}@tastytrade-mcp.local",
            status=UserStatus.ACTIVE,  # This equals "active" (lowercase)
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    
    # Initiate OAuth
    oauth_service = OAuthService(session)
    auth_url, state = await oauth_service.initiate_oauth(
        user_id=user.id,
        is_sandbox=request.is_sandbox,
        redirect_uri=request.redirect_uri,
    )
    
    # Calculate expiration (10 minutes)
    from tastytrade_mcp.auth.oauth_config import get_oauth_config
    config = get_oauth_config()
    expires_at = datetime.utcnow().timestamp() + config.state_ttl_seconds
    
    return OAuthInitiateResponse(
        auth_url=auth_url,
        state=state,
        expires_at=datetime.fromtimestamp(expires_at),
        user_id=user.id,
    )


@router.get("/oauth/callback")
async def oauth_callback(
    state: str = Query(..., description="State for CSRF protection"),
    code: Optional[str] = Query(None, description="Authorization code"),
    error: Optional[str] = Query(None, description="Error from OAuth provider"),
    error_description: Optional[str] = Query(None, description="Error description"),
    session: AsyncSession = Depends(get_session),
):
    """
    Handle OAuth callback from TastyTrade.
    
    Exchanges authorization code for tokens and stores them.
    """
    # Check for errors
    if error:
        logger.error(f"OAuth error: {error} - {error_description}")
        return RedirectResponse(
            url=f"/auth/error?error={error}&description={error_description}",
            status_code=status.HTTP_302_FOUND,
        )
    
    # Check if code is present
    if not code:
        logger.error("OAuth callback missing authorization code")
        return RedirectResponse(
            url="/auth/error?error=missing_code",
            status_code=status.HTTP_302_FOUND,
        )
    
    try:
        # Handle callback
        oauth_service = OAuthService(session)
        broker_link = await oauth_service.handle_callback(code, state)
        
        # Get user
        result = await session.execute(
            select(User).where(User.id == broker_link.user_id)
        )
        user = result.scalar_one()
        
        # Create JWT tokens
        jwt_service = get_jwt_service()
        access_token = jwt_service.create_access_token(
            user_id=user.id,
            broker_linked=True,
            is_sandbox=broker_link.is_sandbox if hasattr(broker_link, 'is_sandbox') else True,
        )
        refresh_token = jwt_service.create_refresh_token(user_id=user.id)
        
        # Redirect to success page with tokens
        # In production, these would be set as secure HTTP-only cookies
        redirect_url = (
            f"/auth/success"
            f"?access_token={access_token}"
            f"&refresh_token={refresh_token}"
        )
        
        return RedirectResponse(
            url=redirect_url,
            status_code=status.HTTP_302_FOUND,
        )
        
    except ValueError as e:
        logger.error(f"OAuth callback error: {e}")
        return RedirectResponse(
            url=f"/auth/error?error=invalid_state",
            status_code=status.HTTP_302_FOUND,
        )
    except Exception as e:
        logger.error(f"Unexpected OAuth callback error: {e}")
        return RedirectResponse(
            url=f"/auth/error?error=server_error",
            status_code=status.HTTP_302_FOUND,
        )


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status(
    current_user: Optional[User] = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
) -> AuthStatusResponse:
    """
    Get current authentication status.
    
    Returns user info if authenticated, basic status otherwise.
    """
    if not current_user:
        return AuthStatusResponse(
            authenticated=False,
        )
    
    # Check broker link
    result = await session.execute(
        select(BrokerLink).where(
            BrokerLink.user_id == current_user.id,
            BrokerLink.provider == "tastytrade",
        )
    )
    broker_link = result.scalar_one_or_none()
    
    broker_linked = broker_link is not None and broker_link.status == LinkStatus.ACTIVE
    
    # TODO: Get accounts from TastyTrade API
    accounts = []
    
    # Check subscription
    # TODO: Implement subscription check
    subscription_active = current_user.is_free_access
    
    return AuthStatusResponse(
        authenticated=True,
        user_id=current_user.id,
        broker_linked=broker_linked,
        subscription_active=subscription_active,
        is_sandbox=broker_link.is_sandbox if broker_link and hasattr(broker_link, 'is_sandbox') else True,
        accounts=accounts,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """
    Refresh access token using refresh token.
    
    Returns new access and refresh tokens.
    """
    jwt_service = get_jwt_service()
    
    # Verify refresh token
    token_data = jwt_service.verify_token(request.refresh_token, token_type="refresh")
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    # Get user
    result = await session.execute(
        select(User).where(User.id == UUID(token_data.sub))
    )
    user = result.scalar_one_or_none()
    
    if not user or user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    # Check broker link status
    result = await session.execute(
        select(BrokerLink).where(
            BrokerLink.user_id == user.id,
            BrokerLink.provider == "tastytrade",
        )
    )
    broker_link = result.scalar_one_or_none()
    broker_linked = broker_link is not None and broker_link.status == LinkStatus.ACTIVE
    
    # Create new tokens
    new_access_token = jwt_service.create_access_token(
        user_id=user.id,
        broker_linked=broker_linked,
    )
    new_refresh_token = jwt_service.create_refresh_token(user_id=user.id)
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=jwt_service.access_token_expire_minutes * 60,
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Logout user by revoking OAuth tokens.
    
    Revokes TastyTrade OAuth tokens but keeps user account.
    """
    # Get broker link
    result = await session.execute(
        select(BrokerLink).where(
            BrokerLink.user_id == current_user.id,
            BrokerLink.provider == "tastytrade",
        )
    )
    broker_link = result.scalar_one_or_none()
    
    if broker_link:
        oauth_service = OAuthService(session)
        try:
            await oauth_service.revoke_tokens(broker_link)
        except Exception as e:
            logger.error(f"Error revoking tokens: {e}")
    
    # Note: JWT tokens remain valid until expiry
    # In production, you might want to add them to a blacklist
    
    return {"message": "Logged out successfully"}