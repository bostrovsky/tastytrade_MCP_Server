"""Scanning and opportunities response formatters."""
import json
from datetime import datetime
from typing import Any


async def format_opportunities_response(opportunities: list[dict], strategy_type: str, format_type: str = "text") -> str:
    """Format trading opportunities response based on requested format."""
    if format_type == "json":
        return json.dumps({
            "opportunities": opportunities,
            "strategy_type": strategy_type,
            "total_results": len(opportunities),
            "timestamp": datetime.utcnow().isoformat()
        }, indent=2, default=str)

    # Text format
    if not opportunities:
        return (
            f"No {strategy_type.replace('_', ' ')} opportunities found with the specified criteria.\n\n"
            "Suggestions:\n"
            "- Try lowering the minimum return requirement\n"
            "- Increase the maximum DTE\n"
            "- Reduce the minimum volume filter\n"
            "- Add more symbols to your watchlist\n"
        )

    lines = [f"{strategy_type.replace('_', ' ').title()} Opportunities:\n"]

    for i, opp in enumerate(opportunities, 1):
        symbol = opp.get('symbol', 'N/A')
        stock_price = opp.get('stock_price', 0)
        dte = opp.get('dte', 0)
        return_percent = opp.get('return_percent', 0)

        lines.append(f"{i}. {symbol} (${stock_price:.2f})")

        if strategy_type == "covered_call":
            strike = opp.get('strike', 0)
            premium = opp.get('premium', 0)
            max_profit = opp.get('max_profit', 0)
            volume = opp.get('volume', 0)

            lines.append(f"   Call Strike: ${strike:.2f}")
            lines.append(f"   Premium: ${premium:.2f}")
            lines.append(f"   Max Profit: ${max_profit:.2f}")
            lines.append(f"   Return: {return_percent:.2f}%")
            lines.append(f"   DTE: {dte} days")
            lines.append(f"   Volume: {volume}")

        elif strategy_type == "cash_secured_put":
            strike = opp.get('strike', 0)
            premium = opp.get('premium', 0)
            cash_required = opp.get('cash_required', 0)
            volume = opp.get('volume', 0)

            lines.append(f"   Put Strike: ${strike:.2f}")
            lines.append(f"   Premium: ${premium:.2f}")
            lines.append(f"   Cash Required: ${cash_required:,.2f}")
            lines.append(f"   Return: {return_percent:.2f}%")
            lines.append(f"   DTE: {dte} days")
            lines.append(f"   Volume: {volume}")

        elif strategy_type == "strangles":
            put_strike = opp.get('put_strike', 0)
            call_strike = opp.get('call_strike', 0)
            total_premium = opp.get('total_premium', 0)
            put_volume = opp.get('put_volume', 0)
            call_volume = opp.get('call_volume', 0)

            lines.append(f"   Put Strike: ${put_strike:.2f}")
            lines.append(f"   Call Strike: ${call_strike:.2f}")
            lines.append(f"   Total Premium: ${total_premium:.2f}")
            lines.append(f"   Return: {return_percent:.2f}%")
            lines.append(f"   DTE: {dte} days")
            lines.append(f"   Put Volume: {put_volume}, Call Volume: {call_volume}")

        lines.append("")

    lines.append(f"Total Opportunities: {len(opportunities)}")
    lines.append(f"Strategy: {strategy_type.replace('_', ' ').title()}")

    return "\n".join(lines)