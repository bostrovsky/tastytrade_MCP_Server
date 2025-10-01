"""OAuth HTTP Client for TastyTrade API.

This module provides direct API access using OAuth2 authentication,
bypassing the TastyTrade SDK which doesn't support OAuth.
"""

import time
import httpx
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class OAuthHTTPClient:
    """Direct TastyTrade API client using OAuth2 authentication.

    This client handles:
    - OAuth token refresh (15-minute expiry)
    - Automatic retry on 401 errors
    - Connection pooling for performance
    - Both sandbox and production environments
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        sandbox: bool = True
    ):
        """Initialize OAuth client with credentials.

        Args:
            client_id: OAuth application client ID
            client_secret: OAuth application client secret
            refresh_token: Long-lived refresh token
            sandbox: Use sandbox environment (default True)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[float] = None
        self.sandbox = sandbox

        # API URLs
        self.base_url = (
            "https://api.cert.tastyworks.com"
            if sandbox
            else "https://api.tastyworks.com"
        )

        # OAuth token endpoint (same for both environments)
        self.oauth_url = (
            "https://api.cert.tastyworks.com/oauth/token"
            if sandbox
            else "https://api.tastyworks.com/oauth/token"
        )

        # HTTP client with connection pooling for better performance
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )

        logger.info(f"OAuth client initialized for {'sandbox' if sandbox else 'production'} environment")

    async def ensure_valid_token(self) -> None:
        """Ensure we have a valid access token, refreshing if needed.

        Tokens expire after 15 minutes. We refresh 60 seconds before expiry
        to avoid any edge cases with clock skew.
        """
        if not self.access_token or self.token_expired():
            logger.info("Access token missing or expired, refreshing...")
            await self.refresh_access_token()

    def token_expired(self) -> bool:
        """Check if token is expired or will expire soon.

        Returns:
            True if token needs refresh, False otherwise
        """
        if not self.token_expires_at:
            return True

        # Refresh 60 seconds before actual expiry
        buffer_seconds = 60
        return time.time() >= (self.token_expires_at - buffer_seconds)

    async def refresh_access_token(self) -> None:
        """Get new access token using refresh token.

        Raises:
            Exception: If token refresh fails
        """
        # Use a separate client for the OAuth endpoint
        async with httpx.AsyncClient() as oauth_client:
            logger.debug("Requesting new access token...")

            response = await oauth_client.post(
                self.oauth_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
            )

        if response.status_code != 200:
            error_msg = f"Token refresh failed: {response.status_code} - {response.text}"
            logger.error(error_msg)

            # Check for specific error about expired refresh token
            if "grant_id" in response.text.lower():
                raise Exception(
                    "Refresh token has expired. Please update TASTYTRADE_REFRESH_TOKEN in .env "
                    "with a new token from TastyTrade API settings."
                )
            raise Exception(error_msg)

        data = response.json()
        self.access_token = data["access_token"]

        # Token expires in 900 seconds (15 minutes)
        expires_in = data.get("expires_in", 900)
        self.token_expires_at = time.time() + expires_in

        # Update refresh token if a new one is provided (rotating tokens)
        if "refresh_token" in data and data["refresh_token"] != self.refresh_token:
            logger.info("New refresh token received, updating...")
            self.refresh_token = data["refresh_token"]
            # Save to .env file for persistence
            self._update_refresh_token_in_env(data["refresh_token"])

        logger.info(f"Access token refreshed, expires in {expires_in} seconds")

    def _update_refresh_token_in_env(self, new_token: str) -> None:
        """Update the refresh token in the .env file for persistence.

        Args:
            new_token: The new refresh token to save
        """
        import os
        from pathlib import Path

        env_path = Path.cwd() / '.env'
        if not env_path.exists():
            logger.warning(".env file not found, cannot persist refresh token")
            return

        try:
            # Read current .env
            lines = []
            token_updated = False

            with open(env_path, 'r') as f:
                for line in f:
                    if line.startswith('TASTYTRADE_REFRESH_TOKEN='):
                        lines.append(f'TASTYTRADE_REFRESH_TOKEN={new_token}\n')
                        token_updated = True
                    else:
                        lines.append(line)

            # Write back if we found and updated the token
            if token_updated:
                with open(env_path, 'w') as f:
                    f.writelines(lines)
                # Also update current environment
                os.environ['TASTYTRADE_REFRESH_TOKEN'] = new_token
                logger.info("Successfully persisted new refresh token to .env")
            else:
                logger.warning("TASTYTRADE_REFRESH_TOKEN not found in .env")
        except Exception as e:
            logger.error(f"Failed to update .env with new refresh token: {e}")

    async def request(
        self,
        method: str,
        endpoint: str,
        retry_on_401: bool = True,
        **kwargs
    ) -> httpx.Response:
        """Make authenticated API request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., "/accounts")
            retry_on_401: Whether to retry on 401 errors
            **kwargs: Additional arguments for httpx.request

        Returns:
            httpx.Response object

        Raises:
            httpx.HTTPStatusError: For non-2xx responses after retries
        """
        # Ensure we have a valid token
        await self.ensure_valid_token()

        # Add auth header
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"

        # Make request
        logger.debug(f"{method} {endpoint}")
        response = await self.client.request(
            method,
            endpoint,
            headers=headers,
            **kwargs
        )

        # Handle 401 with single retry
        if response.status_code == 401 and retry_on_401:
            logger.warning(f"Got 401 on {method} {endpoint}, refreshing token and retrying...")
            await self.refresh_access_token()
            headers["Authorization"] = f"Bearer {self.access_token}"
            response = await self.client.request(
                method,
                endpoint,
                headers=headers,
                **kwargs
            )

        return response

    async def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """GET request with JSON response.

        Args:
            endpoint: API endpoint
            **kwargs: Additional request arguments

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: For non-2xx responses
        """
        response = await self.request("GET", endpoint, **kwargs)
        response.raise_for_status()
        return response.json()

    async def post(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """POST request with JSON response.

        Args:
            endpoint: API endpoint
            **kwargs: Additional request arguments

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: For non-2xx responses
        """
        response = await self.request("POST", endpoint, **kwargs)
        response.raise_for_status()
        return response.json()

    async def put(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """PUT request with JSON response.

        Args:
            endpoint: API endpoint
            **kwargs: Additional request arguments

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: For non-2xx responses
        """
        response = await self.request("PUT", endpoint, **kwargs)
        response.raise_for_status()
        return response.json()

    async def delete(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """DELETE request with JSON response.

        Args:
            endpoint: API endpoint
            **kwargs: Additional request arguments

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: For non-2xx responses
        """
        response = await self.request("DELETE", endpoint, **kwargs)
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close the HTTP client connection pool."""
        await self.client.aclose()
        logger.info("OAuth client connection closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()