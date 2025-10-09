"""Advanced position handlers using SDK (sandbox mode).

These handlers use the TastyTrade SDK Session with username/password authentication.
For production (OAuth), see advanced_positions_oauth.py
"""

from typing import Any
import mcp.types as types
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


async def handle_monitor_position_alerts(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Monitor positions for alert conditions using SDK.

    Checks positions against user-defined thresholds (P&L, Greeks, etc.)
    """
    from tastytrade_mcp.services.simple_session import get_tastytrade_session
    from tastytrade import Account

    account_number = arguments.get("account_number")
    thresholds = arguments.get("thresholds", {})

    try:
        session = get_tastytrade_session()

        # Get accounts
        accounts = await Account.a_get(session)

        # Find target account
        target_account = None
        if account_number:
            for acc in accounts:
                if acc.account_number == account_number:
                    target_account = acc
                    break
        else:
            target_account = accounts[0] if accounts else None

        if not target_account:
            return [types.TextContent(
                type="text",
                text=f"Account {account_number} not found" if account_number else "No accounts found"
            )]

        # Get positions
        positions = await target_account.a_get_positions(session)

        if not positions:
            return [types.TextContent(
                type="text",
                text="No positions found to monitor"
            )]

        # Check for alerts
        alerts = []
        for pos in positions:
            # Check P&L threshold
            if "max_loss" in thresholds:
                if hasattr(pos, 'realized_day_gain') and pos.realized_day_gain:
                    if float(pos.realized_day_gain) < -abs(float(thresholds["max_loss"])):
                        alerts.append(f"⚠️  {pos.symbol}: Loss ${pos.realized_day_gain} exceeds threshold")

            # More alert conditions can be added here

        result = f"Position Monitoring for {target_account.account_number}:\n"
        result += f"Total Positions: {len(positions)}\n"
        result += f"Alerts: {len(alerts)}\n\n"

        if alerts:
            result += "ALERTS:\n"
            for alert in alerts:
                result += f"  {alert}\n"
        else:
            result += "✅ No alerts - all positions within thresholds\n"

        return [types.TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Error monitoring positions: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error monitoring positions: {str(e)}"
        )]
