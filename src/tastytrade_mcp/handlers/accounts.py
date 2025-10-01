"""Account-related handlers for TastyTrade MCP."""
from typing import Any
import mcp.types as types
from tastytrade import Account

from tastytrade_mcp.handlers.handler_adapter import HandlerAdapter
from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)

settings = get_settings()
adapter = HandlerAdapter(use_database=settings.use_database_mode)


async def handle_get_accounts(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get accounts for a user.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - format: Optional response format ('text' or 'json')

    Returns:
        List containing TextContent with account information
    """
    user_id = arguments.get("user_id", "default")
    format_type = arguments.get("format", "text")

    try:
        session = await adapter.get_session(user_id)

        # Get accounts - OAuth session needs direct API call
        if hasattr(session, '_get'):
            # Using OAuth session
            response = session._get('/customers/me/accounts')
            if 'data' in response and 'items' in response['data']:
                accounts_data = response['data']['items']
            else:
                accounts_data = []
        else:
            # Using standard session
            accounts = Account.get(session)
            accounts_data = [{'account-number': acc.account_number,
                            'nickname': acc.nickname,
                            'account-type-name': acc.account_type_name,
                            'opened-at': str(acc.opened_at)} for acc in accounts]

        account_list = []
        if hasattr(session, '_get'):
            # Format OAuth response
            for acc in accounts_data:
                account_list.append({
                    'account_number': acc.get('account-number', ''),
                    'account_type': acc.get('account-type-name', 'Unknown'),
                    'nickname': acc.get('nickname', ''),
                    'opened_at': str(acc.get('opened-at', ''))
                })
        else:
            # Format standard session response
            for acc in accounts:
                account_list.append({
                    'account_number': acc.account_number,
                    'account_type': acc.account_type_name or 'Unknown',
                    'nickname': acc.nickname or '',
                    'opened_at': str(acc.opened_at) if acc.opened_at else ''
                })

        if format_type == "json":
            import json
            formatted = json.dumps(account_list, indent=2)
        else:
            if not account_list:
                formatted = "No accounts found"
            else:
                formatted = "\n".join([
                    f"Account {acc['account_number']}: {acc['account_type']}" +
                    (f" ({acc['nickname']})" if acc['nickname'] else "")
                    for acc in account_list
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
            - user_id: The user ID (optional in simple mode)
            - account_number: The account number (optional, will use first account if not provided)
            - format: Optional response format ('text' or 'json')

    Returns:
        List containing TextContent with balance information
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")
    format_type = arguments.get("format", "text")

    try:
        session = await adapter.get_session(user_id)

        if not account_number:
            account_number = await adapter.get_account_number(user_id)

        # Get accounts - OAuth session needs direct API call
        if hasattr(session, '_get'):
            # Using OAuth session
            response = session._get('/customers/me/accounts')
            if 'data' in response and 'items' in response['data']:
                accounts_data = response['data']['items']
            else:
                accounts_data = []
        else:
            # Using standard session
            accounts = Account.get(session)
            accounts_data = [{'account-number': acc.account_number,
                            'nickname': acc.nickname,
                            'account-type-name': acc.account_type_name,
                            'opened-at': str(acc.opened_at)} for acc in accounts]
        # For OAuth session, get balances directly via API
        if hasattr(session, '_get'):
            try:
                # Get balances for the specific account
                balances_response = session._get(f'/accounts/{account_number}/balances')
                if 'data' in balances_response:
                    balances_data = balances_response['data']
                else:
                    return [types.TextContent(
                        type="text",
                        text=f"⚠️ Unable to retrieve complete balance data for account {account_number}.\n"
                             f"Note: Full balance details are only available during market hours (9:30 AM - 4:00 PM ET)."
                    )]
            except Exception as e:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Error retrieving balances: {str(e)}\n"
                         f"Note: Some TastyTrade data is only available during market hours."
                )]
        else:
            # Standard session - find the account
            target_account = None
            for acc in accounts:
                if acc.account_number == account_number:
                    target_account = acc
                    break

            if not target_account:
                return [types.TextContent(
                    type="text",
                    text=f"Account {account_number} not found"
                )]

            balances_data = target_account.get_balances(session)

        # Format balance info based on session type
        if hasattr(session, '_get') and isinstance(balances_data, dict):
            # OAuth response format
            balance_info = {
                'account_number': account_number,
                'cash_balance': balances_data.get('cash-balance', 0),
                'net_liquidating_value': balances_data.get('net-liquidating-value', 0),
                'equity_buying_power': balances_data.get('equity-buying-power', 0),
                'maintenance_requirement': balances_data.get('maintenance-requirement', 0),
                'cash_available_for_trading': balances_data.get('cash-available-for-trading', 0),
            }
        else:
            # Standard session format
            balance_info = {
                'account_number': account_number,
                'cash_balance': balances_data.cash_balance if hasattr(balances_data, 'cash_balance') else 0,
                'net_liquidating_value': balances_data.net_liquidating_value if hasattr(balances_data, 'net_liquidating_value') else 0,
                'equity_buying_power': balances_data.equity_buying_power if hasattr(balances_data, 'equity_buying_power') else 0,
            }

        if format_type == "json":
            import json
            formatted = json.dumps(balance_info, indent=2)
        else:
            formatted = f"Account {account_number} Balance:\n"
            formatted += f"  Cash: ${balance_info['cash_balance']:.2f}\n"
            formatted += f"  Net Liquidating Value: ${balance_info['net_liquidating_value']:.2f}\n"
            formatted += f"  Equity Buying Power: ${balance_info['equity_buying_power']:.2f}\n"

        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error getting balances: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error retrieving balances: {str(e)}"
        )]