"""Authentication router - routes to correct auth method based on environment."""
import os
from typing import Tuple, Optional
from tastytrade import Session
from tastytrade_mcp.services.oauth_client import OAuthHTTPClient
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


def get_auth_method() -> Tuple[str, dict]:
    """Determine which authentication method to use based on environment.

    Returns:
        Tuple of (auth_type, credentials_dict)
        - auth_type: 'oauth' or 'password'
        - credentials_dict: Dict with required credentials
    """
    use_production = os.getenv('TASTYTRADE_USE_PRODUCTION', 'false').lower() == 'true'

    if use_production:
        # Production: Use OAuth
        client_id = os.getenv('TASTYTRADE_CLIENT_ID')
        client_secret = os.getenv('TASTYTRADE_CLIENT_SECRET')
        refresh_token = os.getenv('TASTYTRADE_REFRESH_TOKEN')

        if not all([client_id, client_secret, refresh_token]):
            raise ValueError(
                "Production mode requires OAuth credentials: "
                "TASTYTRADE_CLIENT_ID, TASTYTRADE_CLIENT_SECRET, TASTYTRADE_REFRESH_TOKEN"
            )

        logger.info("🔐 Using OAuth authentication for PRODUCTION")
        return 'oauth', {
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'sandbox': False
        }
    else:
        # Sandbox: Use username/password
        username = os.getenv('TASTYTRADE_SANDBOX_USERNAME')
        password = os.getenv('TASTYTRADE_SANDBOX_PASSWORD')

        if not all([username, password]):
            raise ValueError(
                "Sandbox mode requires credentials: "
                "TASTYTRADE_SANDBOX_USERNAME, TASTYTRADE_SANDBOX_PASSWORD"
            )

        logger.info("🔐 Using username/password authentication for SANDBOX")
        return 'password', {
            'username': username,
            'password': password,
            'is_test': True
        }


async def get_session():
    """Get authenticated session using correct method for environment.

    Returns:
        Session: Authenticated TastyTrade session (SDK Session object)
    """
    auth_type, creds = get_auth_method()

    if auth_type == 'password':
        # Username/password authentication (sandbox)
        session = Session(
            creds['username'],
            creds['password'],
            is_test=creds['is_test']
        )
        logger.info("✅ Authenticated to SANDBOX via username/password")
        return session
    else:
        # OAuth authentication (production)
        # Note: OAuthHTTPClient is different from Session
        # This will need special handling in handlers
        raise NotImplementedError(
            "OAuth session creation through this helper not yet implemented. "
            "Use OAuthHTTPClient directly in handlers."
        )


def get_oauth_client():
    """Get OAuthHTTPClient for OAuth-based authentication.

    Returns:
        OAuthHTTPClient: Configured OAuth client

    Raises:
        ValueError: If not in production mode or credentials missing
    """
    auth_type, creds = get_auth_method()

    if auth_type != 'oauth':
        raise ValueError("OAuth client only available in production mode")

    return OAuthHTTPClient(
        client_id=creds['client_id'],
        client_secret=creds['client_secret'],
        refresh_token=creds['refresh_token'],
        sandbox=creds['sandbox']
    )
