"""OAuth Session implementation for TastyTrade."""
import os
import httpx
from typing import Optional, Any, Dict
from tastytrade.session import API_URL, CERT_URL
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class OAuthSession:
    """
    OAuth-based session for TastyTrade API.

    This class mimics the interface of tastytrade.Session but uses OAuth tokens
    instead of username/password authentication.
    """

    def __init__(self, access_token: str, is_test: bool = False):
        """
        Initialize OAuth session with access token.

        Args:
            access_token: OAuth access token
            is_test: Whether to use test/sandbox environment
        """
        self.session_token = access_token
        self.is_test = is_test

        # Set up API URLs
        self.api_url = CERT_URL if is_test else API_URL

        # Create httpx client with OAuth header
        self._client = httpx.Client(
            base_url=self.api_url,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=30.0
        )

        logger.info(f"OAuthSession initialized for {'SANDBOX' if is_test else 'PRODUCTION'}")

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Make GET request to API."""
        response = self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, json: Optional[Dict[str, Any]] = None) -> Any:
        """Make POST request to API."""
        response = self._client.post(path, json=json)
        response.raise_for_status()
        return response.json()

    def _put(self, path: str, json: Optional[Dict[str, Any]] = None) -> Any:
        """Make PUT request to API."""
        response = self._client.put(path, json=json)
        response.raise_for_status()
        return response.json()

    def _delete(self, path: str) -> Any:
        """Make DELETE request to API."""
        response = self._client.delete(path)
        response.raise_for_status()
        return response.json() if response.content else None

    async def _a_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Async GET - for compatibility, just calls sync version."""
        return self._get(path, params)

    async def _a_post(self, path: str, json: Optional[Dict[str, Any]] = None) -> Any:
        """Async POST - for compatibility, just calls sync version."""
        return self._post(path, json)

    async def _a_put(self, path: str, json: Optional[Dict[str, Any]] = None) -> Any:
        """Async PUT - for compatibility, just calls sync version."""
        return self._put(path, json)

    async def _a_delete(self, path: str) -> Any:
        """Async DELETE - for compatibility, just calls sync version."""
        return self._delete(path)

    def validate(self) -> bool:
        """Validate session - OAuth tokens are pre-validated."""
        return True

    async def a_validate(self) -> bool:
        """Async validate - OAuth tokens are pre-validated."""
        return True

    def destroy(self):
        """Close the session."""
        if hasattr(self, '_client'):
            self._client.close()

    async def a_destroy(self):
        """Async close the session."""
        self.destroy()

    def get_customer(self) -> dict:
        """Get customer info."""
        return self._get('/customers/me')

    async def a_get_customer(self) -> dict:
        """Async get customer info."""
        return await self._a_get('/customers/me')


def create_oauth_session(access_token: str, use_production: bool = True) -> OAuthSession:
    """
    Create an OAuth-based session for TastyTrade API.

    Args:
        access_token: OAuth access token
        use_production: Whether to use production (True) or sandbox (False)

    Returns:
        OAuthSession configured with the access token
    """
    return OAuthSession(access_token, is_test=not use_production)