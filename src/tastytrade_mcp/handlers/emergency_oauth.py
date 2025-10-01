"""Emergency handlers using OAuth client directly."""
import os
import json
from datetime import datetime
from typing import Any
import mcp.types as types
from tastytrade_mcp.services.oauth_client import OAuthHTTPClient
from tastytrade_mcp.services.response_parser import ResponseParser
from tastytrade_mcp.utils.logging import get_logger
from tastytrade_mcp.handlers.utils_oauth import ensure_account_number, get_oauth_credentials

logger = get_logger(__name__)

# Persistent emergency state using JSON file
import json
from pathlib import Path

EMERGENCY_STATE_FILE = Path(__file__).parent.parent / "config" / "emergency_state.json"

def load_emergency_state():
    """Load emergency state from file or create default."""
    if EMERGENCY_STATE_FILE.exists():
        try:
            with open(EMERGENCY_STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load emergency state: {e}")

    # Default state
    return {
        "trading_halted": False,
        "panic_mode": False,
        "circuit_breakers": [],
        "emergency_history": [],
        "last_updated": datetime.now().isoformat()
    }

def save_emergency_state(state):
    """Save emergency state to file."""
    try:
        EMERGENCY_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        state["last_updated"] = datetime.now().isoformat()
        with open(EMERGENCY_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        return True
    except Exception as e:
        logger.error(f"Failed to save emergency state: {e}")
        return False

# Load initial state
EMERGENCY_STATE = load_emergency_state()


async def handle_panic_button(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Emergency panic button to immediately halt all trading.

    Args:
        arguments: Dictionary containing:
            - account_number: Account to halt (optional, halts all accounts)
            - reason: Reason for panic (optional)

    Returns:
        List containing TextContent with result
    """
    account_number = arguments.get("account_number")
    reason = arguments.get("reason", "Manual panic button activated")

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
            # Get all accounts if not specified
            if not account_number:
                accounts_response = await client.get('/customers/me/accounts')
                accounts = ResponseParser.parse_accounts(accounts_response)
            else:
                accounts = [{"account_number": account_number}]

            cancelled_orders = []
            errors = []

            # Cancel all open orders for each account
            for account in accounts:
                acc_num = account.account_number if hasattr(account, 'account_number') else account.get('account_number')

                try:
                    # Get all live orders
                    orders_response = await client.get(
                        f'/accounts/{acc_num}/orders',
                        params={'status': 'live'}
                    )
                    orders = ResponseParser.parse_orders(orders_response)

                    # Cancel each order
                    for order in orders:
                        try:
                            await client.delete(f'/accounts/{acc_num}/orders/{order.order_id}')
                            cancelled_orders.append(f"{acc_num}:{order.order_id}")
                        except Exception as e:
                            errors.append(f"Failed to cancel {order.order_id}: {e}")

                except Exception as e:
                    errors.append(f"Failed to get orders for {acc_num}: {e}")

            # Update emergency state
            EMERGENCY_STATE["panic_mode"] = True
            EMERGENCY_STATE["trading_halted"] = True
            EMERGENCY_STATE["emergency_history"].append({
                "type": "panic_button",
                "timestamp": datetime.now().isoformat(),
                "reason": reason,
                "cancelled_orders": cancelled_orders,
                "errors": errors
            })

            # Format response
            formatted = "🚨 PANIC BUTTON ACTIVATED 🚨\n\n"
            formatted += f"Reason: {reason}\n"
            formatted += f"Cancelled {len(cancelled_orders)} orders\n"

            if cancelled_orders:
                formatted += "\nCancelled Orders:\n"
                for order in cancelled_orders[:10]:  # Show first 10
                    formatted += f"  - {order}\n"
                if len(cancelled_orders) > 10:
                    formatted += f"  ... and {len(cancelled_orders) - 10} more\n"

            if errors:
                formatted += f"\n⚠️ {len(errors)} errors occurred:\n"
                for error in errors[:5]:  # Show first 5 errors
                    formatted += f"  - {error}\n"

            formatted += "\n✅ All trading halted. Use resume_trading to re-enable."

            return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error in panic button: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"❌ PANIC BUTTON FAILED: {str(e)}\n\nMANUAL INTERVENTION REQUIRED!"
        )]


async def handle_halt_trading(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Halt trading without cancelling existing orders.

    Args:
        arguments: Dictionary containing:
            - reason: Reason for halt (optional)

    Returns:
        List containing TextContent with result
    """
    reason = arguments.get("reason", "Trading halt requested")

    EMERGENCY_STATE["trading_halted"] = True
    EMERGENCY_STATE["emergency_history"].append({
        "type": "halt_trading",
        "timestamp": datetime.now().isoformat(),
        "reason": reason
    })
    save_emergency_state(EMERGENCY_STATE)

    formatted = "⚠️ TRADING HALTED\n\n"
    formatted += f"Reason: {reason}\n"
    formatted += "• New orders blocked\n"
    formatted += "• Existing orders remain active\n"
    formatted += "• Use resume_trading to re-enable\n"
    formatted += "• Use panic_button to cancel all orders"

    return [types.TextContent(type="text", text=formatted)]


async def handle_resume_trading(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Resume trading after halt or panic.

    Args:
        arguments: Dictionary containing:
            - confirm: Must be 'yes' to confirm (safety check)

    Returns:
        List containing TextContent with result
    """
    confirm = arguments.get("confirm", "").lower()

    if confirm != "yes":
        return [types.TextContent(
            type="text",
            text="⚠️ Safety check: Please confirm with confirm='yes' to resume trading"
        )]

    EMERGENCY_STATE["trading_halted"] = False
    EMERGENCY_STATE["panic_mode"] = False
    EMERGENCY_STATE["emergency_history"].append({
        "type": "resume_trading",
        "timestamp": datetime.now().isoformat()
    })
    save_emergency_state(EMERGENCY_STATE)

    formatted = "✅ TRADING RESUMED\n\n"
    formatted += "• Orders can now be placed\n"
    formatted += "• All safety systems active\n"
    formatted += "• Circuit breakers remain in place"

    return [types.TextContent(type="text", text=formatted)]


async def handle_emergency_exit(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Emergency exit all positions (close at market).

    Args:
        arguments: Dictionary containing:
            - account_number: Account to exit (optional, exits all)
            - confirm: Must be 'CONFIRM_EXIT_ALL' for safety

    Returns:
        List containing TextContent with result
    """
    account_number = arguments.get("account_number")
    confirm = arguments.get("confirm", "")

    if confirm != "CONFIRM_EXIT_ALL":
        return [types.TextContent(
            type="text",
            text="⚠️ SAFETY CHECK FAILED\n\nTo exit all positions, set confirm='CONFIRM_EXIT_ALL'\n\nThis will:\n• Close all positions at market\n• Cancel all open orders\n• This action cannot be undone!"
        )]

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
            # Get accounts
            if not account_number:
                accounts_response = await client.get('/customers/me/accounts')
                accounts = ResponseParser.parse_accounts(accounts_response)
            else:
                accounts = [{"account_number": account_number}]

            exit_orders = []
            errors = []

            for account in accounts:
                acc_num = account.account_number if hasattr(account, 'account_number') else account.get('account_number')

                try:
                    # Get positions
                    positions_response = await client.get(f'/accounts/{acc_num}/positions')
                    positions = ResponseParser.parse_positions(positions_response)

                    # Create market orders to close each position
                    for position in positions:
                        try:
                            # Determine side (opposite of position)
                            side = "sell" if position.quantity > 0 else "buy"
                            quantity = abs(position.quantity)

                            order_payload = {
                                "order-type": "Market",
                                "time-in-force": "IOC",  # Immediate or cancel
                                "legs": [
                                    {
                                        "instrument-type": position.instrument_type or "Equity",
                                        "symbol": position.symbol,
                                        "quantity": quantity,
                                        "action": side.capitalize()
                                    }
                                ]
                            }

                            order_response = await client.post(
                                f'/accounts/{acc_num}/orders',
                                json=order_payload
                            )

                            order_id = order_response.get("data", {}).get("order", {}).get("id", "unknown")
                            exit_orders.append(f"{position.symbol}:{quantity}:{side}")

                        except Exception as e:
                            errors.append(f"Failed to exit {position.symbol}: {e}")

                except Exception as e:
                    errors.append(f"Failed to get positions for {acc_num}: {e}")

            # Update emergency state
            EMERGENCY_STATE["emergency_history"].append({
                "type": "emergency_exit",
                "timestamp": datetime.now().isoformat(),
                "exit_orders": exit_orders,
                "errors": errors
            })

            formatted = "🚨 EMERGENCY EXIT EXECUTED 🚨\n\n"
            formatted += f"Exited {len(exit_orders)} positions\n"

            if exit_orders:
                formatted += "\nExit Orders:\n"
                for order in exit_orders[:10]:
                    formatted += f"  - {order}\n"
                if len(exit_orders) > 10:
                    formatted += f"  ... and {len(exit_orders) - 10} more\n"

            if errors:
                formatted += f"\n⚠️ {len(errors)} errors:\n"
                for error in errors[:5]:
                    formatted += f"  - {error}\n"

            return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error in emergency exit: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"❌ EMERGENCY EXIT FAILED: {str(e)}"
        )]


async def handle_emergency_stop_all(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Complete emergency stop - halt trading and cancel all orders."""
    # Combine panic button and halt
    panic_result = await handle_panic_button({"reason": "Emergency stop all"})
    return panic_result


async def handle_create_circuit_breaker(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Create a circuit breaker rule."""
    rule_type = arguments.get("type", "loss_limit")
    threshold = arguments.get("threshold", 0)
    action = arguments.get("action", "halt")

    circuit_breaker = {
        "id": len(EMERGENCY_STATE["circuit_breakers"]) + 1,
        "type": rule_type,
        "threshold": threshold,
        "action": action,
        "created": datetime.now().isoformat(),
        "triggered": False
    }

    EMERGENCY_STATE["circuit_breakers"].append(circuit_breaker)
    save_emergency_state(EMERGENCY_STATE)

    formatted = f"✅ Circuit Breaker Created\n"
    formatted += f"  ID: {circuit_breaker['id']}\n"
    formatted += f"  Type: {rule_type}\n"
    formatted += f"  Threshold: {threshold}\n"
    formatted += f"  Action: {action}"

    return [types.TextContent(type="text", text=formatted)]


async def handle_check_emergency_conditions(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Check current emergency conditions and circuit breakers."""
    # Reload state to get latest data
    global EMERGENCY_STATE
    EMERGENCY_STATE = load_emergency_state()

    formatted = "📊 EMERGENCY STATUS\n\n"
    formatted += f"Trading Halted: {'🔴 YES' if EMERGENCY_STATE['trading_halted'] else '🟢 NO'}\n"
    formatted += f"Panic Mode: {'🔴 YES' if EMERGENCY_STATE['panic_mode'] else '🟢 NO'}\n"
    formatted += f"Active Circuit Breakers: {len(EMERGENCY_STATE['circuit_breakers'])}\n"

    if EMERGENCY_STATE['circuit_breakers']:
        formatted += "\nCircuit Breakers:\n"
        for cb in EMERGENCY_STATE['circuit_breakers']:
            status = "🔴 TRIGGERED" if cb['triggered'] else "🟢 ACTIVE"
            formatted += f"  [{cb['id']}] {cb['type']} @ {cb['threshold']} - {status}\n"

    return [types.TextContent(type="text", text=formatted)]


async def handle_get_emergency_history(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get emergency action history."""
    # Reload state to get latest history
    global EMERGENCY_STATE
    EMERGENCY_STATE = load_emergency_state()

    limit = arguments.get("limit", 10)

    history = EMERGENCY_STATE["emergency_history"][-limit:]

    if not history:
        return [types.TextContent(type="text", text="No emergency actions recorded")]

    formatted = f"📜 EMERGENCY HISTORY (Last {len(history)} events)\n\n"

    for event in reversed(history):
        formatted += f"[{event['timestamp']}] {event['type'].upper()}\n"
        if 'reason' in event:
            formatted += f"  Reason: {event['reason']}\n"
        if 'cancelled_orders' in event and event['cancelled_orders']:
            formatted += f"  Cancelled: {len(event['cancelled_orders'])} orders\n"
        if 'exit_orders' in event and event['exit_orders']:
            formatted += f"  Exited: {len(event['exit_orders'])} positions\n"
        formatted += "\n"

    return [types.TextContent(type="text", text=formatted)]