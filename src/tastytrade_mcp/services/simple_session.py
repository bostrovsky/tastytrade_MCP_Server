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
    Get a TastyTrade session using either username/password OR OAuth tokens.

    Supports two modes:
    1. Simple mode: Username/password authentication (sandbox)
    2. OAuth mode: Refresh token flow (production/sandbox)

    Returns:
        Session: Authenticated TastyTrade session
    """
    global _session, _access_token

    if _session is None:
        settings = get_settings()

        # Check environment FIRST to determine auth method
        use_production = os.getenv('TASTYTRADE_USE_PRODUCTION', 'false').lower() == 'true'

        try:
            if use_production:
                # PRODUCTION: Use OAuth credentials
                client_id = os.getenv('TASTYTRADE_CLIENT_ID')
                client_secret = os.getenv('TASTYTRADE_CLIENT_SECRET')
                refresh_token = os.getenv('TASTYTRADE_REFRESH_TOKEN')

                if not all([client_id, client_secret, refresh_token]):
                    raise ValueError(
                        "Production mode requires OAuth credentials: "
                        "TASTYTRADE_CLIENT_ID, TASTYTRADE_CLIENT_SECRET, TASTYTRADE_REFRESH_TOKEN"
                    )

                logger.info("Using OAuth authentication for PRODUCTION")
                base_url = "https://api.tastyworks.com"

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

                from tastytrade_mcp.services.oauth_session import OAuthSession
                _session = OAuthSession(_access_token, is_test=False)

                logger.info("✅ Successfully authenticated to TastyTrade PRODUCTION via OAuth")

            else:
                # SANDBOX: Use username/password
                sandbox_username = os.getenv('TASTYTRADE_SANDBOX_USERNAME')
                sandbox_password = os.getenv('TASTYTRADE_SANDBOX_PASSWORD')

                if not all([sandbox_username, sandbox_password]):
                    raise ValueError(
                        "Sandbox mode requires credentials: "
                        "TASTYTRADE_SANDBOX_USERNAME, TASTYTRADE_SANDBOX_PASSWORD"
                    )

                logger.info("Using username/password authentication for SANDBOX")

                _session = Session(
                    sandbox_username,
                    sandbox_password,
                    is_test=True
                )

                logger.info("✅ Successfully authenticated to TastyTrade SANDBOX via username/password")

        except Exception as e:
            logger.error(f"Failed to authenticate to TastyTrade: {e}")
            raise

    return _session


def clear_session():
    """Clear the cached session (useful for testing or credential changes)."""
    global _session
    _session = None