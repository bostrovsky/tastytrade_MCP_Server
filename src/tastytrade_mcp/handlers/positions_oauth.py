"""Position handlers using OAuth client directly."""
import os
from typing import Any
import mcp.types as types
from tastytrade_mcp.services.oauth_client import OAuthHTTPClient
from tastytrade_mcp.services.response_parser import ResponseParser
from tastytrade_mcp.utils.logging import get_logger
from tastytrade_mcp.handlers.utils_oauth import ensure_account_number, get_oauth_credentials

logger = get_logger(__name__)


async def handle_get_positions(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get open positions for an account.

    Args:
        arguments: Dictionary containing:
            - account_number: The account number (optional, will use first account if not provided)
            - format: Optional response format ('text' or 'json')

    Returns:
        List containing TextContent with position information
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

            # Get positions for the account
            positions_response = await client.get(f'/accounts/{account_number}/positions')
            positions = ResponseParser.parse_positions(positions_response)

            if format_type == "json":
                import json
                positions_list = [
                    {
                        'symbol': pos.symbol,
                        'quantity': pos.quantity,
                        'average_price': pos.average_price,
                        'market_value': pos.market_value,
                        'unrealized_pl': pos.unrealized_pl,
                        'realized_pl': pos.realized_pl,
                        'position_type': pos.position_type,
                        'instrument_type': pos.instrument_type,
                        'underlying_symbol': pos.underlying_symbol
                    }
                    for pos in positions
                ]
                formatted = json.dumps(positions_list, indent=2)
            else:
                if not positions:
                    formatted = f"No open positions in account {account_number}"
                else:
                    formatted = f"Positions for account {account_number}:\n"
                    for pos in positions:
                        formatted += f"\n  {pos.symbol}:\n"
                        formatted += f"    Quantity: {pos.quantity}\n"
                        formatted += f"    Avg Price: ${pos.average_price:.2f}\n"
                        formatted += f"    Market Value: ${pos.market_value:,.2f}\n"
                        formatted += f"    Unrealized P/L: ${pos.unrealized_pl:+,.2f}\n"
                        if pos.underlying_symbol:
                            formatted += f"    Underlying: {pos.underlying_symbol}\n"

            return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error getting positions: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error retrieving positions: {str(e)}"
        )]