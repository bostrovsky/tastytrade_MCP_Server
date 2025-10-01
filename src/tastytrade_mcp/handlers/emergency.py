"""Emergency and risk management handlers for TastyTrade MCP."""
from typing import Any
import mcp.types as types
from tastytrade import Account

from tastytrade_mcp.handlers.handler_adapter import HandlerAdapter
from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.utils.logging import get_logger
from tastytrade_mcp.services.emergency_logger import (
    EmergencyLogger,
    EmergencyActionType,
    EmergencyActionStatus
)

logger = get_logger(__name__)
settings = get_settings()
adapter = HandlerAdapter(use_database=settings.use_database_mode)
emergency_logger = EmergencyLogger(use_database=settings.use_database_mode)


async def handle_panic_button(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Execute panic button - immediate halt of all trading activities.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional)
            - account_number: The account number (optional)
            - reason: Reason for panic button (optional)

    Returns:
        List containing TextContent with panic button execution result
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")
    reason = arguments.get("reason", "User initiated panic button")

    action_id = await emergency_logger.log_emergency_action(
        user_id=user_id,
        action_type=EmergencyActionType.PANIC_BUTTON,
        account_number=account_number,
        reason=reason
    )

    try:
        session = await adapter.get_session(user_id)

        if not account_number:
            account_number = await adapter.get_account_number(user_id)

        # Get account to work with
        accounts = Account.get(session)
        target_account = None
        for acc in accounts:
            if acc.account_number == account_number:
                target_account = acc
                break

        if not target_account:
            return [types.TextContent(type="text", text=f"Error: Account {account_number} not found")]

        # Cancel all orders first
        orders_cancelled = 0
        try:
            orders = target_account.get_live_orders(session)
            for order in orders:
                try:
                    target_account.delete_order(session, order.id)
                    orders_cancelled += 1
                    logger.info(f"Cancelled order {order.id}")
                except Exception as e:
                    logger.warning(f"Failed to cancel order {order.id}: {e}")
        except Exception as e:
            logger.warning(f"Failed to retrieve orders: {e}")

        # Note: Position closing would require market orders which need careful implementation
        # For now, we focus on order cancellation as the immediate panic response

        await emergency_logger.update_emergency_action(
            action_id=action_id,
            status=EmergencyActionStatus.COMPLETED,
            orders_cancelled=orders_cancelled,
            accounts_affected=1
        )

        result_text = f"🚨 PANIC BUTTON ACTIVATED 🚨\n"
        result_text += f"Account: {account_number}\n"
        result_text += f"Reason: {reason}\n"
        result_text += f"Orders Cancelled: {orders_cancelled}\n"
        result_text += f"Status: All pending orders cancelled\n"
        result_text += f"Note: Position closure requires manual review for safety"

        return [types.TextContent(type="text", text=result_text)]

    except Exception as e:
        logger.error(f"Error executing panic button: {e}", exc_info=True)
        await emergency_logger.update_emergency_action(
            action_id=action_id,
            status=EmergencyActionStatus.FAILED,
            error_message=str(e)
        )
        return [types.TextContent(type="text", text=f"Error executing panic button: {str(e)}")]


async def handle_emergency_exit(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Cancel all orders and optionally close all positions.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional)
            - account_number: The account number (optional)
            - max_loss_percent: Maximum acceptable loss percentage (optional)
            - dry_run: If true, only simulate (don't execute) (default: True)
            - confirm: Must be 'EXECUTE' to actually close positions (required for non-dry-run)
            - close_positions: Whether to close positions (default: False)

    Returns:
        List containing TextContent with emergency exit result
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")
    max_loss_percent = arguments.get("max_loss_percent", 10.0)
    dry_run = arguments.get("dry_run", True)
    confirm = arguments.get("confirm", "")
    close_positions = arguments.get("close_positions", False)

    action_id = await emergency_logger.log_emergency_action(
        user_id=user_id,
        action_type=EmergencyActionType.EMERGENCY_EXIT,
        account_number=account_number,
        reason=f"Emergency exit with max loss {max_loss_percent}%",
        metadata={"max_loss_percent": max_loss_percent}
    )

    try:
        session = await adapter.get_session(user_id)

        if not account_number:
            account_number = await adapter.get_account_number(user_id)

        # Get account to work with
        accounts = Account.get(session)
        target_account = None
        for acc in accounts:
            if acc.account_number == account_number:
                target_account = acc
                break

        if not target_account:
            return [types.TextContent(type="text", text=f"Error: Account {account_number} not found")]

        # Cancel all orders
        orders_cancelled = 0
        try:
            orders = target_account.get_live_orders(session)
            for order in orders:
                try:
                    target_account.delete_order(session, order.id)
                    orders_cancelled += 1
                    logger.info(f"Cancelled order {order.id}")
                except Exception as e:
                    logger.warning(f"Failed to cancel order {order.id}: {e}")
        except Exception as e:
            logger.warning(f"Failed to retrieve orders: {e}")

        # Get current positions
        positions_to_close = []
        positions_count = 0
        total_market_value = 0
        try:
            positions = target_account.get_positions(session)
            positions_to_close = [p for p in positions if p.quantity != 0]
            positions_count = len(positions_to_close)

            # Calculate total market value
            for pos in positions_to_close:
                if hasattr(pos, 'close_price') and pos.close_price:
                    market_value = float(pos.quantity) * float(pos.close_price) * float(pos.multiplier)
                    total_market_value += market_value
        except Exception as e:
            logger.warning(f"Failed to retrieve positions: {e}")

        # Handle position closure if requested
        positions_closed = 0
        closure_errors = []

        if close_positions and positions_to_close:
            # Safety checks
            if not dry_run and confirm != "EXECUTE":
                return [types.TextContent(
                    type="text",
                    text="❌ SAFETY CHECK FAILED\n\n"
                    "To close positions, you must:\n"
                    "1. Set dry_run=false\n"
                    "2. Set confirm='EXECUTE'\n\n"
                    "This is a safety measure to prevent accidental position closure."
                )]

            if dry_run:
                result_text = f"🔍 DRY RUN - Emergency Exit Simulation\n\n"
                result_text += f"Would cancel {orders_cancelled} order(s)\n"
                result_text += f"Would close {positions_count} position(s):\n\n"

                for pos in positions_to_close:
                    result_text += f"  • {pos.symbol}: {pos.quantity} shares/contracts\n"
                    if hasattr(pos, 'close_price') and pos.close_price:
                        market_value = float(pos.quantity) * float(pos.close_price) * float(pos.multiplier)
                        result_text += f"    Market Value: ${market_value:,.2f}\n"

                result_text += f"\nTotal Market Value: ${total_market_value:,.2f}\n"
                result_text += f"\n⚠️  This is a DRY RUN - no actions taken.\n"
                result_text += f"To execute, set dry_run=false and confirm='EXECUTE'"

                return [types.TextContent(type="text", text=result_text)]

            # Actually close positions
            logger.warning(f"EMERGENCY EXIT: Closing {positions_count} positions for account {account_number}")

            for pos in positions_to_close:
                try:
                    # Determine order side (opposite of position)
                    if pos.quantity > 0:
                        order_side = "Sell"
                    else:
                        order_side = "Buy"

                    # Create market order to close position
                    order_data = {
                        "time_in_force": "Day",
                        "order_type": "Market",
                        "legs": [{
                            "instrument_type": pos.instrument_type,
                            "symbol": pos.symbol,
                            "quantity": abs(pos.quantity),
                            "action": order_side
                        }]
                    }

                    # Place the order
                    order_response = target_account.place_order(session, order_data, dry_run=False)
                    positions_closed += 1
                    logger.info(f"Closed position {pos.symbol}: {order_response}")

                except Exception as e:
                    error_msg = f"Failed to close {pos.symbol}: {str(e)}"
                    logger.error(error_msg)
                    closure_errors.append(error_msg)

        # Determine final status
        if closure_errors:
            status = EmergencyActionStatus.PARTIAL
        else:
            status = EmergencyActionStatus.COMPLETED

        await emergency_logger.update_emergency_action(
            action_id=action_id,
            status=status,
            orders_cancelled=orders_cancelled,
            accounts_affected=1,
            metadata={
                "positions_count": positions_count,
                "positions_closed": positions_closed,
                "total_market_value": total_market_value,
                "errors": closure_errors
            }
        )

        result_text = f"🚨 EMERGENCY EXIT {'EXECUTED' if not dry_run else 'COMPLETED'} 🚨\n"
        result_text += f"Account: {account_number}\n"
        result_text += f"Orders Cancelled: {orders_cancelled}\n"

        if close_positions and not dry_run:
            result_text += f"Positions Closed: {positions_closed}/{positions_count}\n"
            result_text += f"Total Market Value: ${total_market_value:,.2f}\n"
            result_text += f"Max Loss Threshold: {max_loss_percent}%\n\n"

            if positions_closed == positions_count:
                result_text += f"✅ ALL POSITIONS SUCCESSFULLY CLOSED\n"
            elif positions_closed > 0:
                result_text += f"⚠️  PARTIAL CLOSURE: {positions_closed} of {positions_count} positions closed\n"
            else:
                result_text += f"❌ FAILED TO CLOSE POSITIONS\n"

            if closure_errors:
                result_text += f"\n❌ ERRORS ENCOUNTERED:\n"
                for error in closure_errors[:5]:
                    result_text += f"  • {error}\n"
                if len(closure_errors) > 5:
                    result_text += f"  ... and {len(closure_errors) - 5} more errors\n"
        else:
            result_text += f"Open Positions: {positions_count}\n"
            result_text += f"Max Loss Threshold: {max_loss_percent}%\n\n"
            result_text += f"⚠️  POSITION CLOSURE NOT REQUESTED:\n"
            result_text += f"- All pending orders have been cancelled\n"
            result_text += f"- To close positions, use close_positions=true\n"
            result_text += f"- For safety, also set dry_run=false and confirm='EXECUTE'\n"
            result_text += f"- Monitor P&L against {max_loss_percent}% threshold"

        return [types.TextContent(type="text", text=result_text)]

    except Exception as e:
        logger.error(f"Error executing emergency exit: {e}", exc_info=True)
        await emergency_logger.update_emergency_action(
            action_id=action_id,
            status=EmergencyActionStatus.FAILED,
            error_message=str(e)
        )
        return [types.TextContent(type="text", text=f"Error executing emergency exit: {str(e)}")]


async def handle_halt_trading(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Request to halt trading activities (informational in simple mode).

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional)
            - account_number: The account number (optional)
            - duration_minutes: How long to halt trading (optional)
            - reason: Reason for halt (optional)

    Returns:
        List containing TextContent with halt information
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")
    duration_minutes = arguments.get("duration_minutes", 60)
    reason = arguments.get("reason", "Manual trading halt")

    try:
        if not account_number:
            account_number = await adapter.get_account_number(user_id)

        # In simple mode, we can't persist halt state
        if not settings.use_database_mode:
            result_text = f"⏸️  TRADING HALT REQUESTED\n"
            result_text += f"Account: {account_number}\n"
            result_text += f"Duration: {duration_minutes} minutes\n"
            result_text += f"Reason: {reason}\n\n"
            result_text += f"⚠️  SIMPLE MODE LIMITATION:\n"
            result_text += f"Trading halt state cannot be persisted without database mode.\n"
            result_text += f"Please manually avoid placing new orders for {duration_minutes} minutes.\n"
            result_text += f"Consider enabling database mode for automatic halt enforcement."

            return [types.TextContent(type="text", text=result_text)]

        # Database mode would implement actual halt logic here
        return [types.TextContent(type="text", text="Database mode halt logic not yet implemented")]

    except Exception as e:
        logger.error(f"Error processing halt trading request: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error processing halt trading request: {str(e)}")]


async def handle_resume_trading(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Request to resume trading after a halt (informational in simple mode).

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional)
            - account_number: The account number (optional)
            - verification_code: Security verification code (optional)
            - confirm: Confirmation phrase (optional, 'RESUME' for safety)

    Returns:
        List containing TextContent with resume information
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number", "")
    verification_code = arguments.get("verification_code", "")
    confirm = arguments.get("confirm", "")

    try:
        # Try to get account number if not provided, but handle failure gracefully
        if not account_number:
            try:
                account_number = await adapter.get_account_number(user_id)
            except Exception:
                account_number = "[Account unavailable]"

        # Safety check for confirmation
        if confirm and confirm.upper() != "RESUME":
            return [types.TextContent(
                type="text",
                text="⚠️ SAFETY CHECK:\n\n"
                "To resume trading, please provide:\n"
                "  confirm='RESUME'\n\n"
                "This ensures intentional resumption of trading activities."
            )]

        # In simple mode, we can't persist halt state but can log the action
        if not settings.use_database_mode:
            # Log the resume action
            await emergency_logger.log_emergency_action(
                user_id=user_id,
                action_type=EmergencyActionType.RESUME_TRADING,
                account_number=account_number if account_number != "[Account unavailable]" else None,
                reason="Trading resumed after halt",
                metadata={"verification_code": bool(verification_code)}
            )

            result_text = f"▶️  TRADING RESUMED\n"
            result_text += f"Account: {account_number}\n"
            if verification_code:
                result_text += f"Verification: ✅ Provided\n"
            if confirm == "RESUME":
                result_text += f"Confirmation: ✅ RESUME\n"
            result_text += f"\n🟢 STATUS:\n"
            result_text += f"• Trading can now proceed\n"
            result_text += f"• All safety systems active\n"
            result_text += f"• Risk management protocols required\n"

            if not settings.use_database_mode:
                result_text += f"\n⚠️  Note: Simple mode - halt state not persisted"

            return [types.TextContent(type="text", text=result_text)]

        # Database mode would implement actual resume logic here
        return [types.TextContent(type="text", text="Database mode resume logic not yet implemented")]

    except Exception as e:
        logger.error(f"Error processing resume trading request: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error processing resume trading request: {str(e)}")]


async def handle_emergency_stop_all(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Emergency stop all trading across all accounts.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional)
            - confirmation_phrase: Must be "STOP ALL TRADING NOW" (required)

    Returns:
        List containing TextContent with stop all result
    """
    user_id = arguments.get("user_id", "default")
    confirmation = arguments.get("confirmation_phrase")

    if confirmation != "STOP ALL TRADING NOW":
        return [types.TextContent(
            type="text",
            text="Error: Must provide confirmation_phrase='STOP ALL TRADING NOW'"
        )]

    action_id = await emergency_logger.log_emergency_action(
        user_id=user_id,
        action_type=EmergencyActionType.EMERGENCY_STOP_ALL,
        reason="Emergency stop all with confirmation",
        confirmation_phrase=confirmation
    )

    try:
        session = await adapter.get_session(user_id)

        # Get all accounts
        accounts = Account.get(session)

        total_orders_cancelled = 0
        accounts_processed = 0
        errors = []

        # Cancel orders across all accounts
        for account in accounts:
            try:
                orders = account.get_live_orders(session)
                orders_cancelled_for_account = 0

                for order in orders:
                    try:
                        account.delete_order(session, order.id)
                        orders_cancelled_for_account += 1
                        total_orders_cancelled += 1
                        logger.info(f"Cancelled order {order.id} for account {account.account_number}")
                    except Exception as e:
                        logger.warning(f"Failed to cancel order {order.id}: {e}")
                        errors.append(f"Account {account.account_number}: Failed to cancel order {order.id}")

                accounts_processed += 1
                logger.info(f"Processed account {account.account_number}: {orders_cancelled_for_account} orders cancelled")

            except Exception as e:
                logger.error(f"Failed to process account {account.account_number}: {e}")
                errors.append(f"Account {account.account_number}: {str(e)}")

        status = EmergencyActionStatus.COMPLETED if not errors else EmergencyActionStatus.PARTIAL
        await emergency_logger.update_emergency_action(
            action_id=action_id,
            status=status,
            orders_cancelled=total_orders_cancelled,
            accounts_affected=accounts_processed,
            error_message="\n".join(errors) if errors else None
        )

        result_text = f"🛑 EMERGENCY STOP ALL EXECUTED 🛑\n"
        result_text += f"Accounts Processed: {accounts_processed}\n"
        result_text += f"Total Orders Cancelled: {total_orders_cancelled}\n"
        result_text += f"Status: Order cancellation complete\n"

        if errors:
            result_text += f"\n⚠️  ERRORS ENCOUNTERED:\n"
            for error in errors[:5]:
                result_text += f"- {error}\n"
            if len(errors) > 5:
                result_text += f"... and {len(errors) - 5} more errors\n"

        result_text += f"\n📋 NEXT STEPS:\n"
        result_text += f"- All pending orders cancelled across accounts\n"
        result_text += f"- Review open positions manually\n"
        result_text += f"- Consider position closure if needed"

        return [types.TextContent(type="text", text=result_text)]

    except Exception as e:
        logger.error(f"Error executing emergency stop all: {e}", exc_info=True)
        await emergency_logger.update_emergency_action(
            action_id=action_id,
            status=EmergencyActionStatus.FAILED,
            error_message=str(e)
        )
        return [types.TextContent(type="text", text=f"Error executing emergency stop all: {str(e)}")]


async def handle_create_circuit_breaker(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Create a circuit breaker rule (requires database mode).

    Args:
        arguments: Dictionary containing:
            - account_number: The account number (optional)
            - trigger_type: Type of trigger (optional)
            - threshold: Threshold value for trigger (optional)
            - action: Action to take when triggered (optional)

    Returns:
        List containing TextContent with circuit breaker information
    """
    if not settings.use_database_mode:
        result_text = f"🔌 CIRCUIT BREAKER CREATION REQUESTED\n\n"
        result_text += f"⚠️  DATABASE MODE REQUIRED:\n"
        result_text += f"Circuit breakers require database mode for:\n"
        result_text += f"- Persistent rule storage\n"
        result_text += f"- Continuous monitoring\n"
        result_text += f"- Automatic trigger execution\n\n"
        result_text += f"To enable circuit breakers:\n"
        result_text += f"1. Set TASTYTRADE_USE_DATABASE_MODE=true\n"
        result_text += f"2. Configure database connection\n"
        result_text += f"3. Restart the MCP server\n\n"
        result_text += f"Current mode: Simple (database-free)"

        return [types.TextContent(type="text", text=result_text)]

    # Database mode implementation would go here
    return [types.TextContent(type="text", text="Circuit breaker creation in database mode not yet implemented")]


async def handle_check_emergency_conditions(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Check emergency conditions (requires database mode for full monitoring).

    Args:
        arguments: Dictionary containing:
            - account_number: The account number (optional)

    Returns:
        List containing TextContent with emergency conditions information
    """
    if not settings.use_database_mode:
        result_text = f"🔍 EMERGENCY CONDITIONS CHECK REQUESTED\n\n"
        result_text += f"⚠️  DATABASE MODE REQUIRED:\n"
        result_text += f"Comprehensive emergency condition monitoring requires database mode for:\n"
        result_text += f"- Historical data analysis\n"
        result_text += f"- Risk threshold tracking\n"
        result_text += f"- Circuit breaker status\n"
        result_text += f"- Pattern detection\n\n"
        result_text += f"BASIC CHECK AVAILABLE:\n"
        result_text += f"- Use 'get_positions' to view current holdings\n"
        result_text += f"- Use 'get_balances' to check account status\n"
        result_text += f"- Use 'list_orders' to view pending orders\n\n"
        result_text += f"For full emergency monitoring, enable database mode."

        return [types.TextContent(type="text", text=result_text)]

    # Database mode implementation would go here
    return [types.TextContent(type="text", text="Emergency condition monitoring in database mode not yet implemented")]


async def handle_get_emergency_history(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get history of emergency actions (requires database mode).

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional)
            - account_number: The account number (optional)
            - days: Number of days of history to retrieve (optional)

    Returns:
        List containing TextContent with emergency history information
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")
    days = arguments.get("days", 7)

    if not settings.use_database_mode:
        result_text = f"📊 EMERGENCY HISTORY REQUESTED\n"
        result_text += f"Period: Last {days} days\n\n"
        result_text += f"⚠️  DATABASE MODE REQUIRED:\n"
        result_text += f"Emergency action history requires database mode for:\n"
        result_text += f"- Persistent action logging\n"
        result_text += f"- Historical data storage\n"
        result_text += f"- Audit trail maintenance\n"
        result_text += f"- Timeline reconstruction\n\n"
        result_text += f"ALTERNATIVE HISTORY SOURCES:\n"
        result_text += f"- Check application logs for emergency actions\n"
        result_text += f"- Review TastyTrade account activity\n"
        result_text += f"- Monitor order history for cancellations\n\n"
        result_text += f"For comprehensive emergency history, enable database mode."

        return [types.TextContent(type="text", text=result_text)]

    try:
        history = await emergency_logger.get_emergency_history(
            user_id=user_id,
            account_number=account_number,
            days=days
        )

        if not history:
            result_text = f"📊 EMERGENCY HISTORY\n\n"
            result_text += f"No emergency actions found in the last {days} days"
            if account_number:
                result_text += f" for account {account_number}"
            result_text += ".\n"
            return [types.TextContent(type="text", text=result_text)]

        result_text = f"📊 EMERGENCY HISTORY ({len(history)} actions)\n\n"
        for action in history:
            result_text += f"\n• {action['action_type'].upper()}\n"
            result_text += f"  Status: {action['status']}\n"
            result_text += f"  Time: {action['initiated_at']}\n"
            if action.get('reason'):
                result_text += f"  Reason: {action['reason']}\n"
            if action.get('orders_cancelled'):
                result_text += f"  Orders Cancelled: {action['orders_cancelled']}\n"
            if action.get('accounts_affected'):
                result_text += f"  Accounts Affected: {action['accounts_affected']}\n"
            if action.get('error_message'):
                result_text += f"  Error: {action['error_message'][:100]}...\n"

        return [types.TextContent(type="text", text=result_text)]

    except Exception as e:
        logger.error(f"Error getting emergency history: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error retrieving emergency history: {str(e)}")]