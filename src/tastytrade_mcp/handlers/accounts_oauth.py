"""Account handlers using OAuth client directly."""
import os
from typing import Any
import mcp.types as types
from tastytrade_mcp.services.oauth_client import OAuthHTTPClient
from tastytrade_mcp.services.response_parser import ResponseParser
from tastytrade_mcp.utils.logging import get_logger
from tastytrade_mcp.handlers.utils_oauth import ensure_account_number, get_oauth_credentials

logger = get_logger(__name__)


async def handle_get_accounts(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get accounts for the authenticated user.

    Args:
        arguments: Dictionary containing:
            - format: Optional response format ('text' or 'json')

    Returns:
        List containing TextContent with account information
    """
    format_type = arguments.get("format", "text")

    try:
        # Get OAuth credentials from environment
        client_id = os.environ.get('TASTYTRADE_CLIENT_ID')
        client_secret = os.environ.get('TASTYTRADE_CLIENT_SECRET')
        refresh_token = os.environ.get('TASTYTRADE_REFRESH_TOKEN')
        use_production = os.environ.get('TASTYTRADE_USE_PRODUCTION', 'false').lower() == 'true'

        if not all([client_id, client_secret, refresh_token]):
            return [types.TextContent(
                type="text",
                text="Error: OAuth credentials not configured. Please set TASTYTRADE_CLIENT_ID, TASTYTRADE_CLIENT_SECRET, and TASTYTRADE_REFRESH_TOKEN in .env"
            )]

        # Create OAuth client
        async with OAuthHTTPClient(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            sandbox=not use_production
        ) as client:
            # Get accounts from the correct endpoint
            response = await client.get('/customers/me/accounts')
            accounts = ResponseParser.parse_accounts(response)

            if format_type == "json":
                import json
                account_list = [
                    {
                        'account_number': acc.account_number,
                        'account_type': acc.account_type,
                        'nickname': acc.nickname or '',
                        'opened_at': str(acc.opened_at) if acc.opened_at else ''
                    }
                    for acc in accounts
                ]
                formatted = json.dumps(account_list, indent=2)
            else:
                if not accounts:
                    formatted = "No accounts found"
                else:
                    formatted = "\n".join([
                        f"Account {acc.account_number}: {acc.account_type}" +
                        (f" ({acc.nickname})" if acc.nickname else "")
                        for acc in accounts
                    ])

            return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error getting accounts: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error retrieving accounts: {str(e)}"
        )]


async def handle_get_balances(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get account balances.

    Args:
        arguments: Dictionary containing:
            - account_number: The account number (optional, will use first account if not provided)
            - format: Optional response format ('text' or 'json')

    Returns:
        List containing TextContent with balance information
    """
    account_number = arguments.get("account_number")
    format_type = arguments.get("format", "text")

    try:
        # Get OAuth credentials from environment
        client_id = os.environ.get('TASTYTRADE_CLIENT_ID')
        client_secret = os.environ.get('TASTYTRADE_CLIENT_SECRET')
        refresh_token = os.environ.get('TASTYTRADE_REFRESH_TOKEN')
        use_production = os.environ.get('TASTYTRADE_USE_PRODUCTION', 'false').lower() == 'true'

        if not all([client_id, client_secret, refresh_token]):
            return [types.TextContent(
                type="text",
                text="Error: OAuth credentials not configured. Please set TASTYTRADE_CLIENT_ID, TASTYTRADE_CLIENT_SECRET, and TASTYTRADE_REFRESH_TOKEN in .env"
            )]

        # Create OAuth client
        async with OAuthHTTPClient(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            sandbox=not use_production
        ) as client:
            # If no account number provided, get the first account
            if not account_number:
                accounts_response = await client.get('/customers/me/accounts')
                accounts = ResponseParser.parse_accounts(accounts_response)

                if not accounts:
                    return [types.TextContent(
                        type="text",
                        text="No accounts found for authenticated user"
                    )]

                account_number = accounts[0].account_number
                logger.info(f"Using first account: {account_number}")

            # Get balances for the account
            balance_response = await client.get(f'/accounts/{account_number}/balances')
            balance = ResponseParser.parse_balances(balance_response, account_number)

            if format_type == "json":
                import json
                balance_info = {
                    'account_number': balance.account_number,
                    'cash_balance': balance.cash_balance,
                    'net_liquidating_value': balance.net_liquidating_value,
                    'buying_power': balance.buying_power,
                    'cash_available_for_trading': balance.cash_available_for_trading,
                    'maintenance_requirement': balance.maintenance_requirement
                }
                formatted = json.dumps(balance_info, indent=2)
            else:
                formatted = f"Account {balance.account_number} Balance:\n"
                formatted += f"  Cash: ${balance.cash_balance:,.2f}\n"
                formatted += f"  Net Liquidating Value: ${balance.net_liquidating_value:,.2f}\n"
                formatted += f"  Buying Power: ${balance.buying_power:,.2f}\n"
                formatted += f"  Cash Available for Trading: ${balance.cash_available_for_trading:,.2f}\n"
                formatted += f"  Maintenance Requirement: ${balance.maintenance_requirement:,.2f}"

            return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error getting balances: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error retrieving balances: {str(e)}"
        )]