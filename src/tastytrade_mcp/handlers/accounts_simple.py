"""Simplified account handlers without database dependency."""
import json
from typing import Any
import mcp.types as types
from tastytrade import Account

from tastytrade_mcp.services.simple_session import get_tastytrade_session
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


async def handle_get_accounts(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get accounts directly from TastyTrade API.

    Args:
        arguments: Dictionary with optional 'format' parameter

    Returns:
        List containing TextContent with account information
    """
    format_type = arguments.get("format", "text")

    try:
        session = get_tastytrade_session()

        # Get accounts using tastytrade SDK
        accounts_list = await Account.a_get(session)

        accounts = []
        for acc in accounts_list:
            accounts.append({
                'account_number': acc.account_number,
                'nickname': acc.nickname,
                'account_type': acc.account_type_name,
                'is_closed': acc.is_closed,
                'margin_or_cash': getattr(acc, 'margin_or_cash', 'Unknown')
            })

        # Format response
        if format_type == "json":
            formatted = json.dumps(accounts, indent=2)
        else:
            if not accounts:
                formatted = "No accounts found."
            else:
                lines = ["TastyTrade Accounts:\n"]
                for acc in accounts:
                    lines.append(f"Account: {acc['account_number']}")
                    lines.append(f"  Nickname: {acc['nickname']}")
                    lines.append(f"  Type: {acc['account_type']}")
                    lines.append(f"  Status: {'CLOSED' if acc['is_closed'] else 'ACTIVE'}")
                    lines.append("")
                formatted = "\n".join(lines)

        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error getting accounts: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error retrieving accounts: {str(e)}"
        )]


async def handle_get_balances(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get account balances directly from TastyTrade API.

    Args:
        arguments: Dictionary containing:
            - account_number: The account number (required)
            - format: Optional response format ('text' or 'json')

    Returns:
        List containing TextContent with balance information
    """
    account_number = arguments.get("account_number")
    if not account_number:
        return [types.TextContent(type="text", text="Error: account_number parameter is required")]

    format_type = arguments.get("format", "text")

    try:
        session = get_tastytrade_session()

        # Get account object
        account = Account(account_number=account_number)

        # Get balances using tastytrade SDK
        balances = await account.a_get_balances(session)

        # Format response
        if format_type == "json":
            formatted = json.dumps(balances.dict(), indent=2)
        else:
            nlv = getattr(balances, 'net_liquidating_value', 0)
            cash = getattr(balances, 'cash_balance', 0)
            buying_power = getattr(balances, 'derivative_buying_power', 0)
            market_value = getattr(balances, 'long_equity_value', 0)

            formatted = f"""Account Balances for {account_number}:

Net Liquidating Value: ${nlv:,.2f}
Cash Balance: ${cash:,.2f}
Total Market Value: ${market_value:,.2f}
Buying Power: ${buying_power:,.2f}
"""

        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error getting balances: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error retrieving balances: {str(e)}"
        )]