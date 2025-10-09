"""Base service for TastyTrade API with core authentication and client management."""
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from tastytrade_mcp.auth.oauth_service import OAuthService
from tastytrade_mcp.models.auth import BrokerLink
from tastytrade_mcp.services.encryption import get_encryption_service
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class BaseTastyTradeService:
    """Base service for TastyTrade API operations with shared authentication and client management."""

    def __init__(self, session: AsyncSession):
        """Initialize base TastyTrade service."""
        self.session = session
        self.base_url = None
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self, broker_link: BrokerLink) -> httpx.AsyncClient:
        """Get or create HTTP client with OAuth token."""
        if self._client is None:
            # Determine base URL based on sandbox flag
            self.base_url = (
                "https://api.cert.tastyworks.com"
                if getattr(broker_link, 'is_sandbox', True)
                else "https://api.tastyworks.com"
            )

            # Get access token
            access_token = await self._get_access_token(broker_link)

            # Create client with auth header
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

        return self._client

    async def _get_access_token(self, broker_link: BrokerLink) -> str:
        """Get access token, refreshing if needed."""
        if not broker_link.broker_secret:
            raise ValueError("No broker secret found")

        # Check if token needs refresh
        if broker_link.broker_secret.access_expires_at:
            time_until_expiry = broker_link.broker_secret.access_expires_at - datetime.utcnow()
            if time_until_expiry < timedelta(minutes=5):
                # Refresh token
                logger.info(f"Refreshing access token for broker_link {broker_link.id}")
                oauth_service = OAuthService(self.session)
                await oauth_service.refresh_tokens(broker_link)
                await self.session.refresh(broker_link)

        # Decrypt and return access token
        encryption = await get_encryption_service()
        access_token = await encryption.decrypt_token(
            broker_link.broker_secret.enc_access_token,
            token_type="access"
        )

        return access_token

    async def _refresh_and_retry(self, broker_link: BrokerLink):
        """Refresh token and reset client."""
        logger.info("Attempting token refresh after 401 error")

        # Clear existing client
        if self._client:
            await self._client.aclose()
            self._client = None

        # Refresh tokens
        oauth_service = OAuthService(self.session)
        await oauth_service.refresh_tokens(broker_link)
        await self.session.refresh(broker_link)

    async def _handle_api_error(self, error: httpx.HTTPStatusError, broker_link: BrokerLink = None) -> bool:
        """
        Handle API errors with automatic retry logic.

        Args:
            error: HTTP error from API call
            broker_link: Broker link for token refresh if needed

        Returns:
            True if error was handled and retry should be attempted, False otherwise
        """
        if error.response.status_code == 401 and broker_link:
            # Token might be invalid, try refresh
            await self._refresh_and_retry(broker_link)
            return True

        # For other errors, don't retry
        return False

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()