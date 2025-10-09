"""Trading handlers for TastyTrade MCP."""
import json
from decimal import Decimal
from typing import Any

import mcp.types as types
from tastytrade import Account
from tastytrade.order import NewOrder, OrderAction, OrderTimeInForce, OrderType as TTOrderType, PriceEffect

from tastytrade_mcp.services.simple_session import get_tastytrade_session
from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def handle_create_order(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Create an order for any instrument type (equity, options, futures, crypto).

    Unified order handler that supports:
    - Equity (stocks)
    - Equity Options (calls/puts, single or multi-leg)
    - Futures (/ES, /CL, etc.)
    - Future Options
    - Cryptocurrency (BTC/USD, etc.)

    Args:
        arguments: Dictionary containing:
            - account_number: Account number (required)
            - legs: List of order legs (required)
                - instrument_type: Equity, Equity Option, Future, Future Option, Cryptocurrency
                - symbol: Trading symbol
                - quantity: Quantity to trade
                - action: Buy to Open, Buy to Close, Sell to Open, Sell to Close
            - order_type: Market, Limit, Stop, Stop Limit, Notional Market (default: Limit)
            - time_in_force: Day, GTC, GTD, IOC, FOK (default: Day)
            - price: Limit price (required for Limit orders)
            - stop_trigger: Stop trigger price (required for Stop orders)
            - price_effect: Debit or Credit (optional, auto-determined if not provided)
            - dry_run: Preview without executing (default: true)

    Returns:
        List containing TextContent with order result
    """
    account_number = arguments.get("account_number")
    legs = arguments.get("legs", [])
    order_type = arguments.get("order_type", "Limit")
    time_in_force = arguments.get("time_in_force", "Day")
    price = arguments.get("price")
    stop_trigger = arguments.get("stop_trigger")
    price_effect = arguments.get("price_effect")
    dry_run = arguments.get("dry_run", True)

    # Validation
    if not account_number:
        return [types.TextContent(type="text", text="Error: account_number is required")]
    if not legs or len(legs) == 0:
        return [types.TextContent(type="text", text="Error: at least one leg is required")]
    if len(legs) > 4:
        return [types.TextContent(type="text", text="Error: maximum 4 legs allowed")]

    # Validate required fields for order types
    if order_type in ["Limit", "Stop Limit"] and not price:
        return [types.TextContent(type="text", text=f"Error: price is required for {order_type} orders")]
    if order_type in ["Stop", "Stop Limit"] and not stop_trigger:
        return [types.TextContent(type="text", text=f"Error: stop_trigger is required for {order_type} orders")]

    try:
        session = get_tastytrade_session()

        # Get account
        accounts = Account.get(session)
        target_account = None
        for acc in accounts:
            if acc.account_number == account_number:
                target_account = acc
                break

        if not target_account:
            return [types.TextContent(type="text", text=f"Account {account_number} not found")]

        # Build order JSON in TastyTrade API format
        order_json = {
            "time-in-force": time_in_force,
            "order-type": order_type,
            "legs": []
        }

        # Add price fields if provided
        if price:
            order_json["price"] = str(price)
        if stop_trigger:
            order_json["stop-trigger"] = str(stop_trigger)

        # Auto-determine price-effect if not provided
        if not price_effect:
            # Simple heuristic: Buy = Debit, Sell = Credit
            first_action = legs[0].get("action", "")
            if "Buy" in first_action:
                price_effect = "Debit"
            elif "Sell" in first_action:
                price_effect = "Credit"

        if price_effect:
            order_json["price-effect"] = price_effect

        # Convert legs to API format
        for leg in legs:
            order_json["legs"].append({
                "instrument-type": leg["instrument_type"],
                "symbol": leg["symbol"],
                "quantity": str(leg["quantity"]),
                "action": leg["action"]
            })

        # Submit order (dry-run or real)
        if dry_run:
            url = f'/accounts/{account_number}/orders/dry-run'
            response = await session._a_post(url, json=order_json)
            result_prefix = "✅ DRY RUN - Order validated successfully!"
            note = "\n\n⚠️  This was a DRY RUN. To execute, set dry_run=false"
        else:
            url = f'/accounts/{account_number}/orders'
            response = await session._a_post(url, json=order_json)
            result_prefix = "✅ ORDER PLACED!"
            note = ""

        # Format response
        result = f"{result_prefix}\n\n"
        result += f"Order Details:\n"
        result += f"  Account: {account_number}\n"
        result += f"  Type: {order_type}\n"
        result += f"  Time in Force: {time_in_force}\n"
        if price:
            result += f"  Price: ${price}\n"
        if stop_trigger:
            result += f"  Stop Trigger: ${stop_trigger}\n"
        if price_effect:
            result += f"  Price Effect: {price_effect}\n"

        result += f"\nLegs:\n"
        for i, leg in enumerate(legs, 1):
            result += f"  {i}. {leg['action']} {leg['quantity']} {leg['instrument_type']} {leg['symbol']}\n"

        result += note

        # Add order ID if available
        if hasattr(response, 'order') and hasattr(response.order, 'id'):
            result += f"\n\nOrder ID: {response.order.id}"

        return [types.TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Error creating order: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error creating order: {str(e)}")]


async def handle_create_equity_order(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Create an equity order.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - account_number: The account number (optional if using adapter default)
            - symbol: Trading symbol (required)
            - side: Order side - Buy or Sell (required)
            - quantity: Number of shares (required)
            - order_type: Order type - Market, Limit, Stop, StopLimit (default: Market)
            - price: Limit price (for limit orders)
            - time_in_force: Time in force - Day, GTC, etc. (default: Day)

    Returns:
        List containing TextContent with order result
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")
    symbol = arguments.get("symbol")
    side = arguments.get("side")
    quantity = arguments.get("quantity")
    order_type = arguments.get("order_type", "Market")
    price = arguments.get("price")
    time_in_force = arguments.get("time_in_force", "Day")

    if not all([symbol, side, quantity]):
        return [types.TextContent(type="text", text="Error: symbol, side, and quantity are required")]

    try:
        session = get_tastytrade_session()

        if not account_number:
            # Get first account if not specified
            accounts = Account.get(session)
            if accounts:
                account_number = accounts[0].account_number

        accounts = Account.get(session)
        target_account = None
        for acc in accounts:
            if acc.account_number == account_number:
                target_account = acc
                break

        if not target_account:
            return [types.TextContent(type="text", text=f"Account {account_number} not found")]

        action = OrderAction.BUY_TO_OPEN if side.lower() in ['buy', 'long'] else OrderAction.SELL_TO_CLOSE

        order_legs = [
            {
                'instrument-type': 'Equity',
                'symbol': symbol.upper(),
                'quantity': int(quantity),
                'action': action
            }
        ]

        order_data = {
            'time-in-force': time_in_force.upper(),
            'order-type': order_type.title(),
            'legs': order_legs
        }

        if price and order_type.lower() in ['limit', 'stop_limit', 'stoplimit']:
            order_data['price'] = str(price)
            order_data['price-effect'] = 'Debit' if action == OrderAction.BUY_TO_OPEN else 'Credit'

        response = target_account.place_order(session, order_data, dry_run=False)

        result_text = f"""✅ Order Submitted:

Symbol: {symbol.upper()}
Side: {side}
Quantity: {quantity}
Order Type: {order_type}
Price: ${price if price else 'Market'}
Time in Force: {time_in_force}

Order details: {json.dumps(response, indent=2)}

Note: Check order status using list_orders tool.
"""
        return [types.TextContent(type="text", text=result_text)]

    except Exception as e:
        logger.error(f"Error creating equity order: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error creating equity order: {str(e)}")]


async def handle_create_options_order(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Create an options order.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - account_number: The account number (optional if using adapter default)
            - underlying_symbol: Underlying symbol (required)
            - legs: List of option legs (required)

    Returns:
        List containing TextContent with options order preview
    """
    user_id = arguments.get("user_id", "default")

    try:
        if settings.use_database_mode:
            return [types.TextContent(type="text", text="Options orders with preview/confirmation require database mode (not yet implemented)")]

        return [types.TextContent(type="text", text="Options orders require database mode for risk analysis and preview. Feature available in database mode only. For now, use direct broker interface for options trading.")]

    except Exception as e:
        logger.error(f"Error creating options order: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error creating options order: {str(e)}")]


async def handle_confirm_order(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Confirm and execute a previewed order.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - preview_token: The preview token from order preview (required)
            - confirmation: Must be "CONFIRM" to execute (required)

    Returns:
        List containing TextContent with order execution result
    """
    user_id = arguments.get("user_id", "default")
    preview_token = arguments.get("preview_token")
    confirmation = arguments.get("confirmation")

    try:
        if settings.use_database_mode:
            return [types.TextContent(type="text", text="Order confirmation with preview tokens requires database mode (not yet implemented)")]

        return [types.TextContent(type="text", text="Order preview/confirmation workflow requires database mode for storing pending orders. In simple mode, orders are placed directly without preview step.")]

    except Exception as e:
        logger.error(f"Error confirming order: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error confirming order: {str(e)}")]


async def handle_cancel_order(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Cancel an existing order.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - account_number: The account number (optional if using adapter default)
            - order_id: The order ID to cancel (required)

    Returns:
        List containing TextContent with cancellation result
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")
    order_id = arguments.get("order_id")

    if not order_id:
        return [types.TextContent(type="text", text="Error: order_id is required")]

    try:
        session = get_tastytrade_session()

        if not account_number:
            # Get first account if not specified
            accounts = Account.get(session)
            if accounts:
                account_number = accounts[0].account_number

        accounts = Account.get(session)
        target_account = None
        for acc in accounts:
            if acc.account_number == account_number:
                target_account = acc
                break

        if not target_account:
            return [types.TextContent(type="text", text=f"Account {account_number} not found")]

        response = target_account.delete_order(session, order_id)

        return [types.TextContent(type="text", text=f"✅ Order {order_id} cancelled successfully. Response: {json.dumps(response, indent=2)}")]

    except Exception as e:
        logger.error(f"Error cancelling order: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error cancelling order: {str(e)}")]


async def handle_list_orders(arguments: dict[str, Any]) -> list[types.TextContent]:
    """List orders for a user.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - account_number: Filter by account number (optional)
            - format: Response format ('text' or 'json')

    Returns:
        List containing TextContent with orders list
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")
    format_type = arguments.get("format", "text")

    try:
        session = get_tastytrade_session()

        if not account_number:
            # Get first account if not specified
            accounts = Account.get(session)
            if accounts:
                account_number = accounts[0].account_number

        accounts = Account.get(session)
        target_account = None
        for acc in accounts:
            if acc.account_number == account_number:
                target_account = acc
                break

        if not target_account:
            return [types.TextContent(type="text", text=f"Account {account_number} not found")]

        orders_data = target_account.get_live_orders(session)

        if format_type == "json":
            orders_list = []
            for order in orders_data:
                orders_list.append({
                    'id': getattr(order, 'id', 'N/A'),
                    'symbol': getattr(order, 'underlying_symbol', 'N/A'),
                    'status': getattr(order, 'status', 'N/A'),
                    'order_type': getattr(order, 'order_type', 'N/A'),
                    'time_in_force': getattr(order, 'time_in_force', 'N/A'),
                    'size': getattr(order, 'size', 0),
                    'price': getattr(order, 'price', None)
                })
            return [types.TextContent(type="text", text=json.dumps(orders_list, indent=2))]

        if not orders_data:
            return [types.TextContent(type="text", text="No active orders found.")]

        lines = ["Active Orders:\n"]
        for order in orders_data:
            lines.append(f"Order ID: {getattr(order, 'id', 'N/A')}")
            lines.append(f"  Symbol: {getattr(order, 'underlying_symbol', 'N/A')}")
            lines.append(f"  Status: {getattr(order, 'status', 'N/A')}")
            lines.append(f"  Type: {getattr(order, 'order_type', 'N/A')}")
            lines.append(f"  Size: {getattr(order, 'size', 0)}")
            if hasattr(order, 'price') and order.price:
                lines.append(f"  Price: ${order.price}")
            lines.append("")

        return [types.TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"Error listing orders: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error listing orders: {str(e)}")]


async def handle_set_stop_loss(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Set a stop-loss order for a position.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - account_number: The account number (optional)
            - symbol: Trading symbol (required)
            - stop_price: Stop price trigger (required)
            - order_type: Order type when triggered (default: market)

    Returns:
        List containing TextContent with stop-loss order result
    """
    user_id = arguments.get("user_id", "default")
    symbol = arguments.get("symbol")
    stop_price = arguments.get("stop_price")

    if not symbol or not stop_price:
        return [types.TextContent(type="text", text="Error: symbol and stop_price are required")]

    try:
        if settings.use_database_mode:
            return [types.TextContent(type="text", text="Stop-loss management requires database mode (not yet implemented)")]

        return [types.TextContent(type="text", text=f"Stop-loss orders require database mode for tracking. For now, manually place a stop order for {symbol} at ${stop_price} using create_equity_order with order_type='Stop'.")]

    except Exception as e:
        logger.error(f"Error setting stop-loss: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error setting stop-loss: {str(e)}")]


async def handle_set_take_profit(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Set a take-profit order for a position.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - account_number: The account number (optional)
            - symbol: Trading symbol (required)
            - target_price: Target price for profit taking (required)

    Returns:
        List containing TextContent with take-profit order result
    """
    user_id = arguments.get("user_id", "default")
    symbol = arguments.get("symbol")
    target_price = arguments.get("target_price")

    if not symbol or not target_price:
        return [types.TextContent(type="text", text="Error: symbol and target_price are required")]

    try:
        if settings.use_database_mode:
            return [types.TextContent(type="text", text="Take-profit management requires database mode (not yet implemented)")]

        return [types.TextContent(type="text", text=f"Take-profit orders require database mode for tracking. For now, manually place a limit order for {symbol} at ${target_price} using create_equity_order with order_type='Limit'.")]

    except Exception as e:
        logger.error(f"Error setting take-profit: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error setting take-profit: {str(e)}")]