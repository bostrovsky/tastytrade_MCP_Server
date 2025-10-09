"""OAuth service for TastyTrade authentication."""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tastytrade_mcp.auth.oauth_config import (
    build_authorization_url,
    get_oauth_config,
    validate_redirect_uri,
)
from tastytrade_mcp.db.session import get_session_context
from tastytrade_mcp.models.auth import BrokerLink, BrokerSecret, LinkStatus, OAuthState
from tastytrade_mcp.models.user import User
from tastytrade_mcp.services.encryption import get_encryption_service
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class OAuthService:
    """Service for managing OAuth authentication flow."""
    
    def __init__(self, session: AsyncSession):
        """Initialize OAuth service."""
        self.session = session
        self.config = get_oauth_config()
    
    async def initiate_oauth(
        self,
        user_id: UUID,
        is_sandbox: bool = True,
        redirect_uri: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Initiate OAuth flow for a user.
        
        Args:
            user_id: User ID initiating OAuth
            is_sandbox: Whether to use sandbox environment
            redirect_uri: Optional custom redirect URI
        
        Returns:
            Tuple of (authorization_url, state)
        
        Raises:
            ValueError: If redirect URI is invalid
        """
        # Validate redirect URI if provided
        if redirect_uri and not validate_redirect_uri(redirect_uri):
            raise ValueError(f"Invalid redirect URI: {redirect_uri}")
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Generate PKCE verifier and challenge
        code_verifier = None
        code_challenge = None
        
        if self.config.use_pkce:
            code_verifier = secrets.token_urlsafe(64)
            # Create S256 challenge
            challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
            code_challenge = base64.urlsafe_b64encode(challenge_bytes).decode().rstrip("=")
        
        # Store OAuth state
        oauth_state = OAuthState(
            id=uuid4(),
            user_id=user_id,
            state=state,
            code_verifier_encrypted=code_verifier or "",  # Encrypt later if needed
            redirect_uri=redirect_uri or self.config.redirect_uri,
            is_sandbox=is_sandbox,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=self.config.state_ttl_seconds),
        )
        
        self.session.add(oauth_state)
        await self.session.commit()
        
        # Build authorization URL
        auth_url = build_authorization_url(
            state=state,
            code_challenge=code_challenge,
            redirect_uri=redirect_uri,
        )
        
        logger.info(
            "OAuth flow initiated",
            extra={
                "user_id": str(user_id),
                "state": state[:8] + "...",
                "is_sandbox": is_sandbox,
            }
        )
        
        return auth_url, state
    
    async def handle_callback(
        self,
        code: str,
        state: str,
    ) -> BrokerLink:
        """
        Handle OAuth callback from TastyTrade.
        
        Args:
            code: Authorization code from callback
            state: State parameter for CSRF protection
        
        Returns:
            Created or updated BrokerLink
        
        Raises:
            ValueError: If state is invalid or expired
            httpx.HTTPError: If token exchange fails
        """
        # Verify state
        result = await self.session.execute(
            select(OAuthState).where(
                OAuthState.state == state,
                OAuthState.expires_at > datetime.utcnow(),
            )
        )
        oauth_state = result.scalar_one_or_none()
        
        if not oauth_state:
            raise ValueError("Invalid or expired OAuth state")
        
        # Exchange code for tokens
        tokens = await self._exchange_code_for_tokens(
            code=code,
            code_verifier=oauth_state.code_verifier_encrypted,  # We'll decrypt if actually encrypted
            redirect_uri=oauth_state.redirect_uri,
        )
        
        # Encrypt tokens
        encryption = await get_encryption_service()
        encrypted_access = await encryption.encrypt_token(
            tokens["access_token"],
            token_type="access",
        )
        encrypted_refresh = await encryption.encrypt_token(
            tokens["refresh_token"],
            token_type="refresh",
        )
        
        # Check for existing broker link
        result = await self.session.execute(
            select(BrokerLink).where(
                BrokerLink.user_id == oauth_state.user_id,
                BrokerLink.provider == "tastytrade",
            )
        )
        broker_link = result.scalar_one_or_none()
        
        if broker_link:
            # Update existing link
            broker_link.status = LinkStatus.ACTIVE
            broker_link.linked_at = datetime.utcnow()
            broker_link.revoked_at = None
            
            # Update secrets
            if broker_link.broker_secret:
                broker_link.broker_secret.enc_access_token = encrypted_access
                broker_link.broker_secret.enc_refresh_token = encrypted_refresh
                broker_link.broker_secret.access_expires_at = datetime.utcnow() + timedelta(
                    seconds=tokens.get("expires_in", 3600)
                )
                broker_link.broker_secret.updated_at = datetime.utcnow()
        else:
            # Create new broker link
            broker_link = BrokerLink(
                id=uuid4(),
                user_id=oauth_state.user_id,
                provider="tastytrade",
                status=LinkStatus.ACTIVE,
                linked_at=datetime.utcnow(),
            )
            
            # Create broker secret
            broker_secret = BrokerSecret(
                id=uuid4(),
                broker_link_id=broker_link.id,
                enc_access_token=encrypted_access,
                enc_refresh_token=encrypted_refresh,
                access_expires_at=datetime.utcnow() + timedelta(
                    seconds=tokens.get("expires_in", 3600)
                ),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            
            broker_link.broker_secret = broker_secret
            self.session.add(broker_link)
            self.session.add(broker_secret)
        
        # Delete used OAuth state
        await self.session.delete(oauth_state)
        await self.session.commit()
        
        logger.info(
            "OAuth callback processed",
            extra={
                "user_id": str(oauth_state.user_id),
                "broker_link_id": str(broker_link.id),
            }
        )
        
        return broker_link
    
    async def _exchange_code_for_tokens(
        self,
        code: str,
        code_verifier: Optional[str],
        redirect_uri: str,
    ) -> dict:
        """
        Exchange authorization code for access tokens.
        
        Args:
            code: Authorization code
            code_verifier: PKCE code verifier
            redirect_uri: Redirect URI used in authorization
        
        Returns:
            Token response from TastyTrade
        
        Raises:
            httpx.HTTPError: If token exchange fails
        """
        data = {
            "grant_type": self.config.grant_type,
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.config.client_id,
        }
        
        # Add client secret if available
        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret
        
        # Add PKCE verifier if used
        if code_verifier and self.config.use_pkce:
            data["code_verifier"] = code_verifier
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.config.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            
        return response.json()
    
    async def setup_personal_grant(
        self,
        user_id: UUID,
        refresh_token: str,
        is_sandbox: bool = False,
    ) -> BrokerLink:
        """
        Setup OAuth using personal grant (refresh token from TastyTrade).

        This is for personal use where the user manually creates an OAuth app
        and grant on my.tastytrade.com, then provides the refresh token.

        Args:
            user_id: User ID setting up the grant
            refresh_token: Refresh token from TastyTrade personal grant
            is_sandbox: Whether using sandbox environment

        Returns:
            Created or updated BrokerLink

        Raises:
            httpx.HTTPError: If initial token request fails
        """
        # Determine token URL based on is_sandbox parameter
        if is_sandbox:
            token_url = "https://api.cert.tastyworks.com/oauth/token"
        else:
            token_url = "https://api.tastyworks.com/oauth/token"

        # Use refresh token to get initial access token
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.config.client_id,
        }

        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            tokens = response.json()

        # Encrypt tokens
        encryption = await get_encryption_service()
        encrypted_access = await encryption.encrypt_token(
            tokens["access_token"],
            token_type="access",
        )
        encrypted_refresh = await encryption.encrypt_token(
            refresh_token,  # Store the original refresh token
            token_type="refresh",
        )

        # Check for existing broker link
        result = await self.session.execute(
            select(BrokerLink).where(
                BrokerLink.user_id == user_id,
                BrokerLink.provider == "tastytrade",
            )
        )
        broker_link = result.scalar_one_or_none()

        if broker_link:
            # Update existing link
            broker_link.status = LinkStatus.ACTIVE
            broker_link.linked_at = datetime.utcnow()
            broker_link.revoked_at = None

            # Update secrets
            if broker_link.broker_secret:
                broker_link.broker_secret.enc_access_token = encrypted_access
                broker_link.broker_secret.enc_refresh_token = encrypted_refresh
                broker_link.broker_secret.access_expires_at = datetime.utcnow() + timedelta(
                    seconds=tokens.get("expires_in", 900)
                )
                broker_link.broker_secret.updated_at = datetime.utcnow()
        else:
            # Create new broker link
            broker_link = BrokerLink(
                id=uuid4(),
                user_id=user_id,
                provider="tastytrade",
                is_sandbox=is_sandbox,
                status=LinkStatus.ACTIVE,
                linked_at=datetime.utcnow(),
            )

            # Create broker secret
            broker_secret = BrokerSecret(
                id=uuid4(),
                broker_link_id=broker_link.id,
                enc_access_token=encrypted_access,
                enc_refresh_token=encrypted_refresh,
                access_expires_at=datetime.utcnow() + timedelta(
                    seconds=tokens.get("expires_in", 900)
                ),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            broker_link.broker_secret = broker_secret
            self.session.add(broker_link)
            self.session.add(broker_secret)

        # Note: Commit is handled by the session context manager
        # Don't manually commit here to avoid greenlet context issues

        logger.info(
            "Personal grant setup completed",
            extra={
                "user_id": str(user_id),
                "broker_link_id": str(broker_link.id),
            }
        )

        return broker_link

    async def refresh_tokens(self, broker_link: BrokerLink) -> None:
        """
        Refresh access token using refresh token.
        
        Args:
            broker_link: BrokerLink to refresh tokens for
        
        Raises:
            ValueError: If no refresh token available
            httpx.HTTPError: If token refresh fails
        """
        if not broker_link.broker_secret:
            raise ValueError("No broker secret found")
        
        # Decrypt refresh token
        encryption = await get_encryption_service()
        refresh_token = await encryption.decrypt_token(
            broker_link.broker_secret.enc_refresh_token,
            token_type="refresh",
        )
        
        # Request new tokens
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.config.client_id,
        }
        
        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.config.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            tokens = response.json()
        
        # Encrypt and update tokens
        encrypted_access = await encryption.encrypt_token(
            tokens["access_token"],
            token_type="access",
        )

        broker_link.broker_secret.enc_access_token = encrypted_access
        broker_link.broker_secret.access_expires_at = datetime.utcnow() + timedelta(
            seconds=tokens.get("expires_in", 3600)
        )

        # Update refresh token if provided
        if "refresh_token" in tokens:
            encrypted_refresh = await encryption.encrypt_token(
                tokens["refresh_token"],
                token_type="refresh",
            )
            broker_link.broker_secret.enc_refresh_token = encrypted_refresh

        broker_link.broker_secret.updated_at = datetime.utcnow()
        # Note: Commit is handled by the session context manager
        # Don't manually commit here to avoid greenlet context issues

        logger.info(
            "Tokens refreshed",
            extra={"broker_link_id": str(broker_link.id)}
        )
    
    async def revoke_tokens(self, broker_link: BrokerLink) -> None:
        """
        Revoke OAuth tokens and unlink broker.
        
        Args:
            broker_link: BrokerLink to revoke
        
        Raises:
            httpx.HTTPError: If revocation fails
        """
        if not broker_link.broker_secret:
            logger.warning("No broker secret to revoke")
            return
        
        # Decrypt access token
        encryption = await get_encryption_service()
        access_token = await encryption.decrypt_token(
            broker_link.broker_secret.enc_access_token,
            token_type="access",
        )
        
        # Revoke token with TastyTrade
        data = {
            "token": access_token,
            "client_id": self.config.client_id,
        }
        
        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.config.revoke_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            # Revocation endpoint may return 200 even if token is already invalid
            if response.status_code not in [200, 204]:
                logger.warning(f"Token revocation returned {response.status_code}")
        
        # Update broker link status
        broker_link.status = LinkStatus.REVOKED
        broker_link.revoked_at = datetime.utcnow()
        
        # Clear tokens
        await self.session.delete(broker_link.broker_secret)
        broker_link.broker_secret = None

        # Note: Commit is handled by the session context manager
        # Don't manually commit here to avoid greenlet context issues

        logger.info(
            "Tokens revoked",
            extra={"broker_link_id": str(broker_link.id)}
        )


async def get_oauth_service() -> OAuthService:
    """Get OAuth service instance."""
    async with get_session_context() as session:
        return OAuthService(session)