"""Simple session manager that uses OAuth tokens."""
import os
import httpx
from typing import Optional
from tastytrade import Session
from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)

_session: Optional[Session] = None
_access_token: Optional[str] = None


def get_tastytrade_session() -> Session:
    """
    Get a TastyTrade session using OAuth tokens.

    Uses refresh token to get new access token if needed.
    Perfect for single-user self-hosted deployments.

    Returns:
        Session: Authenticated TastyTrade session
    """
    global _session, _access_token

    if _session is None:
        settings = get_settings()

        # Get OAuth credentials from environment
        client_id = os.getenv('TASTYTRADE_CLIENT_ID')
        client_secret = os.getenv('TASTYTRADE_CLIENT_SECRET')
        refresh_token = os.getenv('TASTYTRADE_REFRESH_TOKEN')

        if not all([client_id, client_secret, refresh_token]):
            raise ValueError("OAuth credentials not configured. Need CLIENT_ID, CLIENT_SECRET, and REFRESH_TOKEN")

        try:
            # Get production mode from environment variable
            use_production = os.getenv('TASTYTRADE_USE_PRODUCTION', 'true').lower() == 'true'
            base_url = "https://api.tastyworks.com" if use_production else "https://api.cert.tastyworks.com"

            # Use refresh token to get new access token
            logger.info(f"Refreshing OAuth token for {'PRODUCTION' if use_production else 'SANDBOX'}")

            response = httpx.post(
                f"{base_url}/oauth/token",
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': client_id,
                    'client_secret': client_secret
                }
            )

            if response.status_code != 200:
                raise Exception(f"Token refresh failed: {response.text}")

            token_data = response.json()
            _access_token = token_data['access_token']

            # The tastytrade Session class REQUIRES username/password
            # We need to use our custom OAuthSession instead
            from tastytrade_mcp.services.oauth_session import OAuthSession

            _session = OAuthSession(_access_token, is_test=not use_production)

            logger.info(f"✅ Successfully authenticated to TastyTrade {'PRODUCTION' if use_production else 'SANDBOX'} via OAuth")

        except Exception as e:
            logger.error(f"Failed to authenticate to TastyTrade: {e}")
            raise

    return _session


def clear_session():
    """Clear the cached session (useful for testing or credential changes)."""
    global _session
    _session = None