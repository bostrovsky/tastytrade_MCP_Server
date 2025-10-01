"""Account-related response formatters."""
import json
from typing import Any


async def format_accounts_response(accounts: list[dict], format_type: str = "text") -> str:
    """Format accounts response based on requested format."""
    if format_type == "json":
        return json.dumps(accounts, indent=2)

    # Text format
    if not accounts:
        return "No accounts found."

    lines = ["TastyTrade Accounts:\n"]
    for acc in accounts:
        lines.append(f"Account: {acc.get('account-number', 'N/A')}")
        lines.append(f"  Nickname: {acc.get('nickname', 'N/A')}")
        lines.append(f"  Type: {acc.get('account-type-name', 'N/A')}")
        lines.append(f"  Status: {'ACTIVE' if not acc.get('is-closed') else 'CLOSED'}")
        lines.append(f"  Margin/Cash: {acc.get('margin-or-cash', 'N/A')}")
        lines.append("")

    return "\n".join(lines)


async def format_positions_response(positions: list[dict], format_type: str = "text") -> str:
    """Format positions response based on requested format."""
    if format_type == "json":
        return json.dumps(positions, indent=2)

    # Text format
    if not positions:
        return "No positions found in this account."

    lines = ["Current Positions:\n"]
    total_value = 0
    total_pnl = 0

    for pos in positions:
        symbol = pos.get('symbol', 'N/A')
        quantity = pos.get('quantity', 0)
        market_value = pos.get('market-value', 0)
        unrealized_pnl = pos.get('unrealized-p-l', 0)
        unrealized_pnl_pct = pos.get('unrealized-p-l-percent', 0)

        total_value += market_value
        total_pnl += unrealized_pnl

        lines.append(f"{symbol}:")
        lines.append(f"  Quantity: {quantity}")
        lines.append(f"  Market Value: ${market_value:,.2f}")
        lines.append(f"  Unrealized P&L: ${unrealized_pnl:,.2f} ({unrealized_pnl_pct:.2f}%)")
        lines.append("")

    lines.append(f"Total Market Value: ${total_value:,.2f}")
    lines.append(f"Total Unrealized P&L: ${total_pnl:,.2f}")

    return "\n".join(lines)


async def format_positions_with_greeks_response(positions: list[dict], format_type: str = "text") -> str:
    """Format positions with Greeks response based on requested format."""
    if format_type == "json":
        return json.dumps(positions, indent=2)

    # Text format
    if not positions:
        return "No positions found in this account."

    lines = ["Positions with Greeks Analysis:\n"]
    total_value = 0
    total_pnl = 0
    total_delta = 0
    option_count = 0

    for pos in positions:
        symbol = pos.get('symbol', 'N/A')
        quantity = pos.get('quantity', 0)
        market_value = pos.get('market-value', 0)
        unrealized_pnl = pos.get('unrealized-p-l', 0)
        unrealized_pnl_pct = pos.get('unrealized-p-l-percent', 0)

        total_value += market_value
        total_pnl += unrealized_pnl

        lines.append(f"{symbol}:")
        lines.append(f"  Quantity: {quantity}")
        lines.append(f"  Market Value: ${market_value:,.2f}")
        lines.append(f"  Unrealized P&L: ${unrealized_pnl:,.2f} ({unrealized_pnl_pct:.2f}%)")

        # Add Greeks data if available
        greeks = pos.get('greeks')
        if greeks:
            option_count += 1
            lines.append("  Greeks:")

            delta = greeks.get('delta')
            if delta is not None:
                position_delta = delta * quantity
                total_delta += position_delta
                lines.append(f"    Delta: {delta:.4f} (Position: {position_delta:.2f})")

            gamma = greeks.get('gamma')
            if gamma is not None:
                lines.append(f"    Gamma: {gamma:.4f}")

            theta = greeks.get('theta')
            if theta is not None:
                position_theta = theta * quantity
                lines.append(f"    Theta: {theta:.4f} (Position: ${position_theta:.2f}/day)")

            vega = greeks.get('vega')
            if vega is not None:
                position_vega = vega * quantity
                lines.append(f"    Vega: {vega:.4f} (Position: {position_vega:.2f})")

            rho = greeks.get('rho')
            if rho is not None:
                lines.append(f"    Rho: {rho:.4f}")

            iv = greeks.get('implied_volatility')
            if iv is not None:
                lines.append(f"    Implied Vol: {iv:.2%}")

        lines.append("")

    # Portfolio summary
    lines.append("Portfolio Summary:")
    lines.append(f"Total Market Value: ${total_value:,.2f}")
    lines.append(f"Total Unrealized P&L: ${total_pnl:,.2f}")

    if option_count > 0:
        lines.append(f"\nPortfolio Greeks:")
        lines.append(f"Total Delta: {total_delta:.2f}")
        lines.append(f"Option Positions: {option_count}")

    return "\n".join(lines)


async def format_portfolio_analysis_response(analysis: dict, format_type: str = "text") -> str:
    """Format portfolio analysis response based on requested format."""
    if format_type == "json":
        return json.dumps(analysis, indent=2)

    # Text format
    lines = ["Portfolio Analysis Report\n"]

    # Summary
    summary = analysis.get('summary', {})
    lines.append("=== Portfolio Summary ===")
    lines.append(f"Total Market Value: ${summary.get('total_market_value', 0):,.2f}")
    lines.append(f"Total Unrealized P&L: ${summary.get('total_unrealized_pnl', 0):,.2f}")
    lines.append(f"Total Cost Basis: ${summary.get('total_cost_basis', 0):,.2f}")
    lines.append(f"Number of Positions: {summary.get('position_count', 0)}")
    lines.append("")

    # Asset allocation
    allocation = analysis.get('asset_allocation', {})
    if allocation:
        lines.append("=== Asset Allocation ===")
        total_value = allocation.get('total_value', 0)
        if total_value > 0:
            for asset_type, amount in allocation.get('by_asset_type', {}).items():
                percentage = (amount / total_value) * 100 if total_value > 0 else 0
                lines.append(f"{asset_type.title()}: ${amount:,.2f} ({percentage:.1f}%)")
        lines.append("")

    # Greeks analysis (for options)
    greeks = analysis.get('greeks_analysis', {})
    if greeks and greeks.get('option_positions_count', 0) > 0:
        lines.append("=== Portfolio Greeks ===")
        lines.append(f"Option Positions: {greeks.get('option_positions_count', 0)}")

        total_greeks = greeks.get('total_greeks', {})
        if total_greeks:
            delta = total_greeks.get('delta', 0)
            gamma = total_greeks.get('gamma', 0)
            theta = total_greeks.get('theta', 0)
            vega = total_greeks.get('vega', 0)

            lines.append(f"Total Delta: {delta:.2f}")
            lines.append(f"Total Gamma: {gamma:.4f}")
            lines.append(f"Total Theta: ${theta:.2f}/day")
            lines.append(f"Total Vega: {vega:.2f}")
        lines.append("")

    # Risk metrics
    risk = analysis.get('risk_metrics', {})
    if risk:
        lines.append("=== Risk Metrics ===")
        concentration = risk.get('concentration_risk', {})
        if concentration:
            lines.append(f"Largest Position: ${concentration.get('largest_position_value', 0):,.2f}")
            lines.append(f"Largest Position %: {concentration.get('largest_position_percent', 0):.1f}%")
            lines.append(f"Top 5 Positions %: {concentration.get('top_5_percent', 0):.1f}%")
        lines.append("")

    # Underlying analysis
    underlying = analysis.get('underlying_analysis', {})
    if underlying:
        lines.append("=== By Underlying Symbol ===")
        for symbol, data in underlying.items():
            market_value = data.get('total_market_value', 0)
            position_delta = data.get('total_delta', 0)
            position_count = data.get('position_count', 0)

            lines.append(f"{symbol}:")
            lines.append(f"  Positions: {position_count}")
            lines.append(f"  Market Value: ${market_value:,.2f}")
            if position_delta is not None:
                lines.append(f"  Total Delta: {position_delta:.2f}")
            lines.append("")

    return "\n".join(lines)


async def format_balances_response(balances: dict, format_type: str = "text") -> str:
    """Format balances response based on requested format."""
    if format_type == "json":
        return json.dumps(balances, indent=2)

    # Text format
    if not balances:
        return "Balance information not available."

    lines = ["Account Balances:\n"]

    # Key balance metrics
    nlv = balances.get('net-liquidating-value', 0)
    cash = balances.get('cash-balance', 0)
    buying_power = balances.get('buying-power', 0)
    day_trading_bp = balances.get('day-trading-buying-power', 0)
    market_value = balances.get('total-market-value', 0)
    maintenance_req = balances.get('maintenance-requirement', 0)
    maintenance_excess = balances.get('maintenance-excess', 0)

    lines.append(f"Net Liquidating Value: ${nlv:,.2f}")
    lines.append(f"Cash Balance: ${cash:,.2f}")
    lines.append(f"Total Market Value: ${market_value:,.2f}")
    lines.append("")
    lines.append("Buying Power:")
    lines.append(f"  Standard: ${buying_power:,.2f}")
    lines.append(f"  Day Trading: ${day_trading_bp:,.2f}")
    lines.append("")
    lines.append("Margin Requirements:")
    lines.append(f"  Maintenance Requirement: ${maintenance_req:,.2f}")
    lines.append(f"  Maintenance Excess: ${maintenance_excess:,.2f}")

    return "\n".join(lines)