"""OAuth configuration for TastyTrade integration."""
import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode, urlparse

from tastytrade_mcp.config.settings import get_settings


@dataclass
class OAuthConfig:
    """OAuth configuration for TastyTrade."""
    
    # OAuth endpoints
    authorize_url: str
    token_url: str
    revoke_url: str
    
    # Client credentials
    client_id: str
    client_secret: Optional[str]
    
    # OAuth parameters
    redirect_uri: str
    scope: str
    response_type: str = "code"
    grant_type: str = "authorization_code"
    
    # Security
    use_pkce: bool = False  # Not used in personal grant flow
    state_ttl_seconds: int = 600  # 10 minutes
    
    @property
    def is_sandbox(self) -> bool:
        """Check if using sandbox environment."""
        return "sandbox" in self.authorize_url.lower()


def get_oauth_config() -> OAuthConfig:
    """Get OAuth configuration based on environment."""

    # Get fresh settings (not cached at module level)
    settings = get_settings()

    # Determine base URLs
    # OAuth token endpoints use api.tastyworks.com (per official TastyTrade docs)
    # Personal grant flow - no browser authorization needed
    if settings.use_sandbox:
        token_base = "https://api.cert.tastyworks.com"
    else:
        token_base = "https://api.tastyworks.com"
    
    # Get client credentials from environment
    client_id = os.getenv("TASTYTRADE_CLIENT_ID", "")
    client_secret = os.getenv("TASTYTRADE_CLIENT_SECRET")
    
    # Get redirect URI
    redirect_uri = os.getenv(
        "OAUTH_REDIRECT_URI",
        "http://localhost:8000/auth/oauth/callback"
    )
    
    # Define scopes (per TastyTrade OAuth docs: read, trade, openid)
    scope = "read trade"

    return OAuthConfig(
        authorize_url="",  # Not used in personal grant flow
        token_url=f"{token_base}/oauth/token",
        revoke_url=f"{token_base}/oauth/revoke",
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
    )


def build_authorization_url(
    state: str,
    code_challenge: Optional[str] = None,
    redirect_uri: Optional[str] = None,
) -> str:
    """
    Build the OAuth authorization URL.
    
    Args:
        state: CSRF protection state
        code_challenge: PKCE code challenge (optional)
        redirect_uri: Override default redirect URI (optional)
    
    Returns:
        Complete authorization URL
    """
    config = get_oauth_config()
    
    params = {
        "response_type": config.response_type,
        "client_id": config.client_id,
        "redirect_uri": redirect_uri or config.redirect_uri,
        "scope": config.scope,
        "state": state,
    }
    
    # Add PKCE challenge if provided
    if code_challenge and config.use_pkce:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
    
    # Build URL
    return f"{config.authorize_url}?{urlencode(params)}"


def validate_redirect_uri(uri: str) -> bool:
    """
    Validate that a redirect URI is allowed.

    Args:
        uri: Redirect URI to validate

    Returns:
        True if valid, False otherwise
    """
    # Get fresh settings
    settings = get_settings()

    # Parse URIs
    provided = urlparse(uri)
    config = get_oauth_config()
    allowed = urlparse(config.redirect_uri)

    # In development, allow localhost with any port
    if settings.environment == "development":
        if provided.hostname in ["localhost", "127.0.0.1"]:
            return True
    
    # Check exact match for production
    return (
        provided.scheme == allowed.scheme and
        provided.netloc == allowed.netloc and
        provided.path == allowed.path
    )