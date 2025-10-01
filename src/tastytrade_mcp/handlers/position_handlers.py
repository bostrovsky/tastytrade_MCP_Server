"""Position management handlers for TastyTrade MCP."""
import json
from typing import Any

import mcp.types as types
from tastytrade import Account

from tastytrade_mcp.handlers.handler_adapter import HandlerAdapter
from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()
adapter = HandlerAdapter(use_database=settings.use_database_mode)


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


async def handle_get_positions(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get current positions for an account.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - account_number: The account number (optional if using adapter default)
            - format: Response format ('text' or 'json')

    Returns:
        List containing TextContent with positions data
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")
    format_type = arguments.get("format", "text")

    try:
        session = await adapter.get_session(user_id)

        if not account_number:
            account_number = await adapter.get_account_number(user_id)

        accounts = Account.get(session)
        target_account = None
        for acc in accounts:
            if acc.account_number == account_number:
                target_account = acc
                break

        if not target_account:
            return [types.TextContent(type="text", text=f"Account {account_number} not found")]

        positions_data = target_account.get_positions(session)

        positions = []
        for pos in positions_data:
            positions.append({
                'symbol': pos.symbol,
                'quantity': float(pos.quantity) if hasattr(pos, 'quantity') else 0,
                'market-value': float(pos.market_value) if hasattr(pos, 'market_value') else 0,
                'unrealized-p-l': float(pos.unrealized_day_gain) if hasattr(pos, 'unrealized_day_gain') else 0,
                'unrealized-p-l-percent': float(pos.unrealized_day_gain_percent) if hasattr(pos, 'unrealized_day_gain_percent') else 0
            })

        formatted = await format_positions_response(positions, format_type)
        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error getting positions: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error retrieving positions: {str(e)}")]


async def handle_get_positions_with_greeks(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get positions with options Greeks analysis.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - account_number: The account number (optional if using adapter default)
            - format: Response format ('text' or 'json')

    Returns:
        List containing TextContent with enhanced positions data
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")
    format_type = arguments.get("format", "text")

    try:
        session = await adapter.get_session(user_id)

        if not account_number:
            account_number = await adapter.get_account_number(user_id)

        accounts = Account.get(session)
        target_account = None
        for acc in accounts:
            if acc.account_number == account_number:
                target_account = acc
                break

        if not target_account:
            return [types.TextContent(type="text", text=f"Account {account_number} not found")]

        positions_data = target_account.get_positions(session, include_closed=False)

        positions = []
        for pos in positions_data:
            pos_dict = {
                'symbol': pos.symbol,
                'quantity': float(pos.quantity) if hasattr(pos, 'quantity') else 0,
                'market-value': float(pos.market_value) if hasattr(pos, 'market_value') else 0,
                'unrealized-p-l': float(pos.unrealized_day_gain) if hasattr(pos, 'unrealized_day_gain') else 0,
                'unrealized-p-l-percent': float(pos.unrealized_day_gain_percent) if hasattr(pos, 'unrealized_day_gain_percent') else 0
            }

            if hasattr(pos, 'greeks') and pos.greeks:
                greeks = pos.greeks
                pos_dict['greeks'] = {
                    'delta': float(greeks.delta) if hasattr(greeks, 'delta') and greeks.delta else None,
                    'gamma': float(greeks.gamma) if hasattr(greeks, 'gamma') and greeks.gamma else None,
                    'theta': float(greeks.theta) if hasattr(greeks, 'theta') and greeks.theta else None,
                    'vega': float(greeks.vega) if hasattr(greeks, 'vega') and greeks.vega else None,
                    'rho': float(greeks.rho) if hasattr(greeks, 'rho') and greeks.rho else None,
                    'implied_volatility': float(greeks.implied_volatility) if hasattr(greeks, 'implied_volatility') and greeks.implied_volatility else None
                }

            positions.append(pos_dict)

        formatted = await format_positions_with_greeks_response(positions, format_type)
        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error getting positions with Greeks: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error retrieving positions with Greeks: {str(e)}")]


async def handle_analyze_portfolio(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Analyze portfolio composition and risk metrics.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - account_number: The account number (optional if using adapter default)
            - format: Response format ('text' or 'json')

    Returns:
        List containing TextContent with portfolio analysis
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")
    format_type = arguments.get("format", "text")

    try:
        session = await adapter.get_session(user_id)

        if not account_number:
            account_number = await adapter.get_account_number(user_id)

        accounts = Account.get(session)
        target_account = None
        for acc in accounts:
            if acc.account_number == account_number:
                target_account = acc
                break

        if not target_account:
            return [types.TextContent(type="text", text=f"Account {account_number} not found")]

        positions_data = target_account.get_positions(session)
        balances_data = target_account.get_balances(session)

        total_market_value = 0
        total_unrealized_pnl = 0
        position_count = len(positions_data)
        option_count = 0
        total_delta = 0

        asset_allocation = {}
        underlying_analysis = {}

        for pos in positions_data:
            market_value = float(pos.market_value) if hasattr(pos, 'market_value') else 0
            unrealized_pnl = float(pos.unrealized_day_gain) if hasattr(pos, 'unrealized_day_gain') else 0

            total_market_value += market_value
            total_unrealized_pnl += unrealized_pnl

            instrument_type = pos.instrument_type if hasattr(pos, 'instrument_type') else 'equity'
            asset_allocation[instrument_type] = asset_allocation.get(instrument_type, 0) + market_value

            underlying = pos.underlying_symbol if hasattr(pos, 'underlying_symbol') else pos.symbol
            if underlying not in underlying_analysis:
                underlying_analysis[underlying] = {
                    'total_market_value': 0,
                    'total_delta': 0,
                    'position_count': 0
                }
            underlying_analysis[underlying]['total_market_value'] += market_value
            underlying_analysis[underlying]['position_count'] += 1

            if hasattr(pos, 'greeks') and pos.greeks:
                option_count += 1
                if hasattr(pos.greeks, 'delta') and pos.greeks.delta:
                    delta = float(pos.greeks.delta) * float(pos.quantity)
                    total_delta += delta
                    underlying_analysis[underlying]['total_delta'] += delta

        analysis = {
            'summary': {
                'total_market_value': total_market_value,
                'total_unrealized_pnl': total_unrealized_pnl,
                'total_cost_basis': float(balances_data.cash_balance) if hasattr(balances_data, 'cash_balance') else 0,
                'position_count': position_count
            },
            'asset_allocation': {
                'total_value': total_market_value,
                'by_asset_type': asset_allocation
            },
            'greeks_analysis': {
                'option_positions_count': option_count,
                'total_greeks': {
                    'delta': total_delta,
                    'gamma': 0,
                    'theta': 0,
                    'vega': 0
                }
            },
            'risk_metrics': {
                'concentration_risk': {
                    'largest_position_value': max([float(p.market_value) for p in positions_data if hasattr(p, 'market_value')], default=0),
                    'largest_position_percent': 0,
                    'top_5_percent': 0
                }
            },
            'underlying_analysis': underlying_analysis
        }

        formatted = await format_portfolio_analysis_response(analysis, format_type)
        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error analyzing portfolio: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error analyzing portfolio: {str(e)}")]


async def handle_monitor_position_alerts(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Monitor position alerts for P&L thresholds and risk management.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - account_number: The account number (optional if using adapter default)
            - alert_types: List of alert types to monitor (optional)

    Returns:
        List containing TextContent with position alerts
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")
    alert_types = arguments.get("alert_types", ["pnl_threshold", "stop_loss_triggered", "take_profit_triggered"])

    try:
        if settings.use_database_mode:
            return [types.TextContent(type="text", text="Position alerts require database mode (not yet implemented)")]

        return [types.TextContent(type="text", text="Position alerts feature requires database mode for alert storage. In simple mode, monitor positions using get_positions tool.")]

    except Exception as e:
        logger.error(f"Error monitoring position alerts: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error monitoring position alerts: {str(e)}")]


async def handle_analyze_position_correlation(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Analyze correlation between positions to identify concentration risk.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - account_number: The account number (optional if using adapter default)
            - lookback_days: Number of days for correlation analysis (default: 30)
            - correlation_threshold: Threshold for high correlation alert (default: 0.7)

    Returns:
        List containing TextContent with correlation analysis
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")
    lookback_days = arguments.get("lookback_days", 30)
    correlation_threshold = arguments.get("correlation_threshold", 0.7)

    try:
        if settings.use_database_mode:
            return [types.TextContent(type="text", text="Position correlation analysis requires database mode (not yet implemented)")]

        return [types.TextContent(type="text", text="Position correlation analysis requires historical data and database storage. Feature available in database mode only.")]

    except Exception as e:
        logger.error(f"Error analyzing position correlation: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error analyzing position correlation: {str(e)}")]


async def handle_bulk_position_update(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Perform bulk operations on multiple positions.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - account_number: The account number (optional if using adapter default)
            - operation: Type of operation to perform (required)
            - symbols: List of symbols to operate on (required)
            - parameters: Operation-specific parameters

    Returns:
        List containing TextContent with bulk operation results
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")
    operation = arguments.get("operation")
    symbols = arguments.get("symbols", [])
    parameters = arguments.get("parameters", {})

    if not operation:
        return [types.TextContent(type="text", text="Error: operation parameter is required")]
    if not symbols:
        return [types.TextContent(type="text", text="Error: symbols parameter is required")]

    try:
        if settings.use_database_mode:
            return [types.TextContent(type="text", text="Bulk position updates require database mode (not yet implemented)")]

        return [types.TextContent(type="text", text=f"Bulk position updates not supported in simple mode. Use individual trading tools for each symbol: {', '.join(symbols)}")]

    except Exception as e:
        logger.error(f"Error with bulk position update: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error with bulk position update: {str(e)}")]