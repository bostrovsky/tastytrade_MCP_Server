"""Shared utilities for OAuth handlers."""
import os
from typing import Optional, Tuple
from tastytrade_mcp.services.oauth_client import OAuthHTTPClient
from tastytrade_mcp.services.response_parser import ResponseParser
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)

# Cache for default account
_DEFAULT_ACCOUNT_CACHE = {
    "account_number": None,
    "last_check": 0
}


async def get_oauth_credentials() -> Tuple[str, str, str, bool]:
    """Get OAuth credentials from environment.

    Returns:
        Tuple of (client_id, client_secret, refresh_token, use_production)

    Raises:
        ValueError: If credentials are missing
    """
    client_id = os.environ.get('TASTYTRADE_CLIENT_ID')
    client_secret = os.environ.get('TASTYTRADE_CLIENT_SECRET')
    refresh_token = os.environ.get('TASTYTRADE_REFRESH_TOKEN')
    use_production = os.environ.get('TASTYTRADE_USE_PRODUCTION', 'false').lower() == 'true'

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError(
            "OAuth credentials not configured. Please set TASTYTRADE_CLIENT_ID, "
            "TASTYTRADE_CLIENT_SECRET, and TASTYTRADE_REFRESH_TOKEN in .env"
        )

    return client_id, client_secret, refresh_token, use_production


async def get_default_account_number() -> Optional[str]:
    """Get the default account number (preferring funded accounts).

    Returns:
        Account number or None if no accounts
    """
    import time

    # Check cache (valid for 5 minutes)
    if _DEFAULT_ACCOUNT_CACHE["account_number"] and \
       time.time() - _DEFAULT_ACCOUNT_CACHE["last_check"] < 300:
        return _DEFAULT_ACCOUNT_CACHE["account_number"]

    try:
        client_id, client_secret, refresh_token, use_production = await get_oauth_credentials()

        async with OAuthHTTPClient(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            sandbox=not use_production
        ) as client:
            accounts_response = await client.get('/customers/me/accounts')
            accounts = ResponseParser.parse_accounts(accounts_response)

            if accounts:
                # Try to find a funded account
                funded_account = None

                # Check for funded accounts
                for acc in accounts:
                    try:
                        balance_response = await client.get(f'/accounts/{acc.account_number}/balances')
                        balance = ResponseParser.parse_balances(balance_response, acc.account_number)

                        if balance.net_liquidating_value > 0:
                            funded_account = acc.account_number
                            logger.info(f"Found funded account: {funded_account} with ${balance.net_liquidating_value:,.2f}")
                            break
                    except Exception:
                        pass

                # Use funded account if found, otherwise first account
                account_number = funded_account or accounts[0].account_number
                _DEFAULT_ACCOUNT_CACHE["account_number"] = account_number
                _DEFAULT_ACCOUNT_CACHE["last_check"] = time.time()
                logger.info(f"Using default account: {account_number}")
                return account_number

    except Exception as e:
        logger.error(f"Error getting default account: {e}")

    return None


async def ensure_account_number(account_number: Optional[str]) -> str:
    """Ensure we have an account number, getting default if needed.

    Args:
        account_number: Provided account number or None

    Returns:
        Valid account number

    Raises:
        ValueError: If no account available
    """
    if account_number:
        return account_number

    default = await get_default_account_number()
    if not default:
        raise ValueError("No account_number provided and no default account found")

    return default