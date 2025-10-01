"""Trading handlers using OAuth client directly."""
import os
import json
from typing import Any
import mcp.types as types
from tastytrade_mcp.services.oauth_client import OAuthHTTPClient
from tastytrade_mcp.services.response_parser import ResponseParser
from tastytrade_mcp.utils.logging import get_logger
from tastytrade_mcp.handlers.utils_oauth import ensure_account_number, get_oauth_credentials

logger = get_logger(__name__)


async def handle_create_equity_order(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Create an equity order.

    Args:
        arguments: Dictionary containing:
            - account_number: Account to place order in (optional, uses first account)
            - symbol: Stock symbol
            - quantity: Number of shares
            - side: 'buy' or 'sell'
            - order_type: 'market', 'limit', 'stop', 'stop_limit'
            - price: Price for limit orders (optional)
            - stop_price: Stop price for stop orders (optional)
            - time_in_force: 'day', 'gtc', 'ioc', 'fok' (default: 'day')
            - format: Response format (text/json)

    Returns:
        List containing TextContent with order details
    """
    account_number = arguments.get("account_number")
    symbol = arguments.get("symbol", "").upper()
    quantity = arguments.get("quantity", 0)
    side = arguments.get("side", "").lower()
    order_type = arguments.get("order_type", "market").lower()
    price = arguments.get("price")
    stop_price = arguments.get("stop_price")
    time_in_force = arguments.get("time_in_force", "day").lower()
    format_type = arguments.get("format", "text")

    # Validate required fields
    if not symbol:
        return [types.TextContent(type="text", text="Error: Symbol is required")]
    if not quantity or quantity <= 0:
        return [types.TextContent(type="text", text="Error: Valid quantity is required")]
    if side not in ["buy", "sell"]:
        return [types.TextContent(type="text", text="Error: Side must be 'buy' or 'sell'")]

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

            # Build order payload with correct format
            order_payload = {
                "order-type": order_type.replace("_", "-").capitalize(),  # "Limit" not "limit"
                "time-in-force": time_in_force.capitalize(),  # "Day" not "DAY"
                "legs": [
                    {
                        "instrument-type": "Equity",
                        "symbol": symbol,
                        "quantity": quantity,
                        "action": "Buy to Open" if side == "buy" else "Sell to Close"
                    }
                ]
            }

            # Add price fields for limit orders
            if order_type in ["limit", "stop_limit"] and price:
                order_payload["price"] = str(price)
                # Price effect is required - Debit for buy, Credit for sell
                order_payload["price-effect"] = "Debit" if side == "buy" else "Credit"

            # Add stop price for stop orders
            if order_type in ["stop", "stop_limit"] and stop_price:
                order_payload["stop-trigger"] = str(stop_price)

            # Submit order
            order_response = await client.post(
                f'/accounts/{account_number}/orders',
                json=order_payload
            )

            # Parse response
            order_id = order_response.get("data", {}).get("order", {}).get("id", "unknown")
            status = order_response.get("data", {}).get("order", {}).get("status", "submitted")

            if format_type == "json":
                formatted = json.dumps(order_response, indent=2)
            else:
                formatted = f"Order Created Successfully!\n"
                formatted += f"  Order ID: {order_id}\n"
                formatted += f"  Symbol: {symbol}\n"
                formatted += f"  Side: {side.upper()}\n"
                formatted += f"  Quantity: {quantity}\n"
                formatted += f"  Type: {order_type.upper()}\n"
                if price:
                    formatted += f"  Price: ${price:.2f}\n"
                if stop_price:
                    formatted += f"  Stop Price: ${stop_price:.2f}\n"
                formatted += f"  Status: {status}\n"

            return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error creating equity order: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error creating equity order: {str(e)}"
        )]


async def handle_cancel_order(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Cancel an existing order.

    Args:
        arguments: Dictionary containing:
            - account_number: Account number (optional, uses first account)
            - order_id: Order ID to cancel
            - format: Response format (text/json)

    Returns:
        List containing TextContent with cancellation result
    """
    account_number = arguments.get("account_number")
    order_id = arguments.get("order_id")
    format_type = arguments.get("format", "text")

    if not order_id:
        return [types.TextContent(type="text", text="Error: Order ID is required")]

    try:
        # Get OAuth credentials from environment
        client_id = os.environ.get('TASTYTRADE_CLIENT_ID')
        client_secret = os.environ.get('TASTYTRADE_CLIENT_SECRET')
        refresh_token = os.environ.get('TASTYTRADE_REFRESH_TOKEN')
        use_production = os.environ.get('TASTYTRADE_USE_PRODUCTION', 'false').lower() == 'true'

        if not all([client_id, client_secret, refresh_token]):
            return [types.TextContent(
                type="text",
                text="Error: OAuth credentials not configured"
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

            # Cancel the order
            response = await client.delete(f'/accounts/{account_number}/orders/{order_id}')

            if format_type == "json":
                formatted = json.dumps({"status": "cancelled", "order_id": order_id}, indent=2)
            else:
                formatted = f"Order {order_id} successfully cancelled"

            return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error cancelling order: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error cancelling order: {str(e)}"
        )]


async def handle_list_orders(arguments: dict[str, Any]) -> list[types.TextContent]:
    """List orders for an account.

    Args:
        arguments: Dictionary containing:
            - account_number: Account number (optional, uses first account)
            - status: Filter by status (optional: 'live', 'filled', 'cancelled')
            - format: Response format (text/json)

    Returns:
        List containing TextContent with order list
    """
    account_number = arguments.get("account_number")
    status_filter = arguments.get("status")
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
                text="Error: OAuth credentials not configured"
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

            # Get orders
            params = {}
            if status_filter:
                params['status'] = status_filter

            orders_response = await client.get(
                f'/accounts/{account_number}/orders',
                params=params
            )

            orders = ResponseParser.parse_orders(orders_response)

            if format_type == "json":
                orders_list = [
                    {
                        'order_id': o.order_id,
                        'symbol': o.symbol,
                        'quantity': o.quantity,
                        'side': o.side,
                        'type': o.order_type,
                        'status': o.status,
                        'price': o.price,
                        'created': str(o.created_at),
                        'updated': str(o.updated_at)
                    }
                    for o in orders
                ]
                formatted = json.dumps(orders_list, indent=2)
            else:
                if not orders:
                    formatted = f"No orders found for account {account_number}"
                else:
                    formatted = f"Orders for account {account_number}:\n"
                    for o in orders:
                        formatted += f"\n  {o.order_id}:\n"
                        formatted += f"    Symbol: {o.symbol}\n"
                        formatted += f"    Side: {o.side} {o.quantity}\n"
                        formatted += f"    Type: {o.order_type}\n"
                        formatted += f"    Status: {o.status}\n"
                        if o.price:
                            formatted += f"    Price: ${o.price:.2f}\n"
                        formatted += f"    Created: {o.created_at}\n"

            return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error listing orders: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error listing orders: {str(e)}"
        )]


# Placeholder functions for complex order types - need more research on API format
async def handle_create_options_order(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Create an options order."""
    return [types.TextContent(
        type="text",
        text="Options order creation via OAuth API needs implementation. The endpoint is POST /accounts/{account}/orders with complex leg structure."
    )]


async def handle_confirm_order(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Confirm an order preview."""
    return [types.TextContent(
        type="text",
        text="Order confirmation is built into the create order flow. Use dry-run flag for preview functionality."
    )]


async def handle_set_stop_loss(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Set stop loss for a position."""
    return [types.TextContent(
        type="text",
        text="Stop loss can be set using create_equity_order with order_type='stop' and stop_price parameter"
    )]


async def handle_set_take_profit(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Set take profit for a position."""
    return [types.TextContent(
        type="text",
        text="Take profit can be set using create_equity_order with order_type='limit' and price parameter"
    )]