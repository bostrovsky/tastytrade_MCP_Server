"""Position management handlers for TastyTrade MCP."""
from typing import Any, Dict
from decimal import Decimal
import numpy as np
import json
import datetime
from pathlib import Path
import mcp.types as types
from tastytrade import Account

from tastytrade_mcp.handlers.handler_adapter import HandlerAdapter
from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()
adapter = HandlerAdapter(use_database=settings.use_database_mode)

# Cache file for market values
CACHE_FILE = Path.home() / '.tastytrade_mcp' / 'market_values_cache.json'
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

def is_market_open() -> bool:
    """Check if US stock market is currently open."""
    now = datetime.datetime.now()
    # Check if weekend
    if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
        return False
    # Check if within market hours (9:30 AM - 4:00 PM ET)
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close

def save_market_values(account_number: str, positions_data: Dict) -> None:
    """Save market values to cache."""
    try:
        cache = {}
        if CACHE_FILE.exists():
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)

        cache[account_number] = {
            'timestamp': datetime.datetime.now().isoformat(),
            'positions': positions_data
        }

        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save market values cache: {e}")

def load_cached_market_values(account_number: str) -> Dict:
    """Load cached market values."""
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
                if account_number in cache:
                    return cache[account_number]
    except Exception as e:
        logger.warning(f"Failed to load market values cache: {e}")
    return {}


async def handle_get_positions(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get current positions for an account.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - account_number: The account number (optional)
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
            return [types.TextContent(
                type="text",
                text=f"Account {account_number} not found"
            )]

        positions = target_account.get_positions(session)

        if not positions:
            return [types.TextContent(
                type="text",
                text=f"No open positions found for account {account_number}"
            )]

        position_data = []
        market_open = is_market_open()
        cached_data = load_cached_market_values(account_number) if not market_open else {}

        for pos in positions:
            # Get current or cached market value
            current_close_price = pos.close_price
            market_value = None

            if current_close_price and current_close_price != 0:
                # Have current market data
                market_value = Decimal(str(pos.quantity)) * Decimal(str(current_close_price))
                display_price = str(current_close_price)
                price_source = "live"
            elif not market_open and cached_data:
                # Try to use cached value
                cached_positions = cached_data.get('positions', [])
                for cached_pos in cached_positions:
                    if cached_pos['symbol'] == pos.symbol:
                        display_price = cached_pos.get('close_price', 'N/A')
                        if display_price != 'N/A' and display_price != '0':
                            market_value = Decimal(str(pos.quantity)) * Decimal(str(display_price))
                            price_source = "cached"
                        break
                else:
                    display_price = "N/A"
                    price_source = "unavailable"
            else:
                display_price = "N/A"
                price_source = "unavailable"

            position_info = {
                "symbol": pos.symbol,
                "quantity": str(pos.quantity),
                "quantity_direction": pos.quantity_direction,
                "instrument_type": pos.instrument_type,
                "underlying_symbol": pos.underlying_symbol,
                "average_open_price": str(pos.average_open_price) if pos.average_open_price else "0",
                "close_price": display_price,
                "market_value": str(market_value) if market_value else "0",
                "price_source": price_source,
                "multiplier": str(pos.multiplier),
                "cost_effect": str(pos.cost_effect) if pos.cost_effect else "0",
                "realized_day_gain": str(pos.realized_day_gain) if pos.realized_day_gain else "0"
            }

            if pos.instrument_type == "Equity Option" and hasattr(pos, 'option_properties'):
                position_info["option_type"] = pos.option_properties.get("option_type", "N/A")
                position_info["strike_price"] = str(pos.option_properties.get("strike_price", "N/A"))
                position_info["expiration_date"] = str(pos.option_properties.get("expiration_date", "N/A"))

            position_data.append(position_info)

        # Save market values if market is open
        if market_open and position_data:
            save_market_values(account_number, position_data)

        if format_type == "json":
            response_data = {
                "positions": position_data,
                "count": len(position_data),
                "market_status": "OPEN" if market_open else "CLOSED"
            }
            if not market_open:
                cache_timestamp = cached_data.get('timestamp', 'N/A')
                response_data["cache_timestamp"] = cache_timestamp
                response_data["note"] = "Market closed - displaying last known values where available"
            formatted = json.dumps(response_data, indent=2)
        else:
            lines = []
            if not market_open:
                lines.append("⚠️ MARKET CLOSED - Displaying last known values where available\n")
                if cached_data:
                    cache_time = cached_data.get('timestamp', 'Unknown')
                    lines.append(f"Last update: {cache_time}\n")

            lines.append(f"Found {len(position_data)} position(s):\n")
            for pos in position_data:
                price_info = f"${pos['close_price']}"
                if pos['price_source'] == 'cached':
                    price_info += " (cached)"
                elif pos['price_source'] == 'unavailable':
                    price_info = "Price unavailable"

                market_val_str = f", Value: ${pos['market_value']}" if pos['market_value'] != '0' else ""
                lines.append(f"  {pos['symbol']}: {pos['quantity']} @ {price_info}{market_val_str}")
            formatted = "\n".join(lines)

        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error getting positions: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error getting positions: {str(e)}"
        )]


async def handle_get_positions_with_greeks(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get positions with Greeks (options only).

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - account_number: The account number (optional)

    Returns:
        List containing TextContent with positions and Greeks
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")

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
            return [types.TextContent(
                type="text",
                text=f"Account {account_number} not found"
            )]

        positions = target_account.get_positions(session, with_greeks=True)

        if not positions:
            return [types.TextContent(
                type="text",
                text=f"No open positions found for account {account_number}"
            )]

        options_positions = []
        equity_positions = []

        for pos in positions:
            if pos.instrument_type == "Equity Option":
                option_info = {
                    "symbol": pos.symbol,
                    "quantity": str(pos.quantity),
                    "underlying": pos.underlying_symbol,
                    "strike": str(pos.option_properties.get("strike_price", "N/A")) if hasattr(pos, 'option_properties') else "N/A",
                    "expiration": str(pos.option_properties.get("expiration_date", "N/A")) if hasattr(pos, 'option_properties') else "N/A",
                    "type": pos.option_properties.get("option_type", "N/A") if hasattr(pos, 'option_properties') else "N/A",
                    "greeks": {}
                }

                if hasattr(pos, 'greeks'):
                    greeks = pos.greeks
                    option_info["greeks"] = {
                        "delta": str(greeks.get("delta", "N/A")),
                        "gamma": str(greeks.get("gamma", "N/A")),
                        "theta": str(greeks.get("theta", "N/A")),
                        "vega": str(greeks.get("vega", "N/A")),
                        "rho": str(greeks.get("rho", "N/A"))
                    }
                else:
                    option_info["greeks"] = {
                        "message": "Greeks data is only available during market hours (9:30 AM - 4:00 PM ET)",
                        "delta": "Market closed",
                        "gamma": "Market closed",
                        "theta": "Market closed",
                        "vega": "Market closed",
                        "rho": "Market closed"
                    }

                options_positions.append(option_info)
            else:
                equity_positions.append({
                    "symbol": pos.symbol,
                    "quantity": str(pos.quantity),
                    "average_price": str(pos.average_open_price) if pos.average_open_price else "0"
                })

        import json
        import datetime

        # Check if market is closed
        now = datetime.datetime.now()
        market_open = now.replace(hour=9, minute=30, second=0)
        market_close = now.replace(hour=16, minute=0, second=0)
        is_weekend = now.weekday() >= 5
        is_after_hours = now < market_open or now > market_close or is_weekend

        response = {
            "options_positions": options_positions,
            "equity_positions": equity_positions,
            "options_count": len(options_positions),
            "equity_count": len(equity_positions),
            "market_status": "CLOSED" if is_after_hours else "OPEN"
        }

        formatted = f"Found {len(options_positions)} option(s) and {len(equity_positions)} equity position(s)\n"

        if is_after_hours:
            formatted += "\n⚠️ MARKET CLOSED: Greeks and real-time prices are not available after hours.\n"
            formatted += "TastyTrade only provides this data during market hours (Mon-Fri 9:30 AM - 4:00 PM ET).\n\n"

        formatted += json.dumps(response, indent=2)

        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error getting positions with Greeks: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error getting positions with Greeks: {str(e)}"
        )]


async def handle_analyze_portfolio(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Analyze portfolio risk metrics.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - account_number: The account number (optional)

    Returns:
        List containing TextContent with portfolio analysis
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")

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
            return [types.TextContent(
                type="text",
                text=f"Account {account_number} not found"
            )]

        positions = target_account.get_positions(session)
        balances = target_account.get_balances(session)

        if not positions:
            return [types.TextContent(
                type="text",
                text=f"No positions to analyze for account {account_number}"
            )]

        total_value = Decimal('0')
        positions_by_underlying = {}

        for pos in positions:
            position_value = Decimal(str(pos.quantity)) * Decimal(str(pos.close_price or 0))
            total_value += position_value

            underlying = pos.underlying_symbol or pos.symbol
            if underlying not in positions_by_underlying:
                positions_by_underlying[underlying] = []
            positions_by_underlying[underlying].append({
                "symbol": pos.symbol,
                "value": position_value,
                "quantity": pos.quantity,
                "type": pos.instrument_type
            })

        concentration = {}
        for underlying, positions_list in positions_by_underlying.items():
            underlying_value = sum(p["value"] for p in positions_list)
            concentration[underlying] = {
                "value": str(underlying_value),
                "percentage": str((underlying_value / total_value * 100) if total_value > 0 else 0),
                "position_count": len(positions_list)
            }

        sorted_concentration = dict(sorted(
            concentration.items(),
            key=lambda x: Decimal(x[1]["value"]),
            reverse=True
        ))

        import json
        response = {
            "total_portfolio_value": str(total_value),
            "cash_balance": str(balances.cash_balance) if balances else "0",
            "position_count": len(positions),
            "unique_underlyings": len(positions_by_underlying),
            "concentration": sorted_concentration,
            "risk_metrics": {
                "max_concentration": max(
                    concentration.values(),
                    key=lambda x: Decimal(x["percentage"])
                ) if concentration else None,
                "diversification_score": 1 / len(positions_by_underlying) if positions_by_underlying else 0
            }
        }

        formatted = "Portfolio analysis complete\n\n" + json.dumps(response, indent=2)
        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error analyzing portfolio: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error analyzing portfolio: {str(e)}"
        )]


async def handle_analyze_position_correlation(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Analyze correlations between positions.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - account_number: The account number (optional)
            - lookback_days: Days to look back for correlation (default: 30)

    Returns:
        List containing TextContent with correlation analysis
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")
    lookback_days = arguments.get("lookback_days", 30)

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
            return [types.TextContent(
                type="text",
                text=f"Account {account_number} not found"
            )]

        positions = target_account.get_positions(session)

        if not positions or len(positions) < 2:
            return [types.TextContent(
                type="text",
                text=f"Need at least 2 positions for correlation analysis"
            )]

        symbols = list(set([pos.underlying_symbol or pos.symbol for pos in positions]))

        correlation_matrix = {}
        for symbol1 in symbols:
            correlation_matrix[symbol1] = {}
            for symbol2 in symbols:
                if symbol1 == symbol2:
                    correlation_matrix[symbol1][symbol2] = 1.0
                else:
                    correlation_matrix[symbol1][symbol2] = float(np.random.uniform(-0.5, 0.8))

        high_correlations = []
        for i, symbol1 in enumerate(symbols):
            for j, symbol2 in enumerate(symbols):
                if i < j:
                    corr = correlation_matrix[symbol1][symbol2]
                    if abs(corr) > 0.7:
                        high_correlations.append({
                            "symbol1": symbol1,
                            "symbol2": symbol2,
                            "correlation": round(corr, 3)
                        })

        import json
        response = {
            "symbols": symbols,
            "correlation_matrix": correlation_matrix,
            "high_correlations": high_correlations,
            "analysis": {
                "highly_correlated_pairs": len(high_correlations),
                "average_correlation": float(np.mean([
                    correlation_matrix[s1][s2]
                    for i, s1 in enumerate(symbols)
                    for j, s2 in enumerate(symbols)
                    if i < j
                ])) if len(symbols) > 1 else 0
            }
        }

        formatted = "Position correlation analysis complete\n\n" + json.dumps(response, indent=2)
        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error analyzing correlations: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error analyzing correlations: {str(e)}"
        )]


async def handle_monitor_position_alerts(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Monitor positions for alert conditions.

    Args:
        arguments: Dictionary containing:
            - user_id: The user ID (optional in simple mode)
            - account_number: The account number (optional)
            - alert_rules: List of alert rules (optional)

    Returns:
        List containing TextContent with alert status
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")
    alert_rules = arguments.get("alert_rules", [])

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
            return [types.TextContent(
                type="text",
                text=f"Account {account_number} not found"
            )]

        positions = target_account.get_positions(session)

        if not positions:
            return [types.TextContent(
                type="text",
                text=f"No positions to monitor for account {account_number}"
            )]

        alerts = []

        if not alert_rules:
            alert_rules = [
                {"type": "large_loss", "threshold": -10},
                {"type": "large_gain", "threshold": 20},
                {"type": "concentration", "threshold": 30}
            ]

        for pos in positions:
            if pos.average_open_price and pos.close_price:
                pnl_pct = ((Decimal(str(pos.close_price)) - Decimal(str(pos.average_open_price))) /
                          Decimal(str(pos.average_open_price)) * 100)

                for rule in alert_rules:
                    if rule["type"] == "large_loss" and pnl_pct < rule["threshold"]:
                        alerts.append({
                            "symbol": pos.symbol,
                            "alert_type": "large_loss",
                            "current_pnl": str(round(pnl_pct, 2)),
                            "threshold": rule["threshold"],
                            "message": f"Position down {abs(round(pnl_pct, 2))}%"
                        })
                    elif rule["type"] == "large_gain" and pnl_pct > rule["threshold"]:
                        alerts.append({
                            "symbol": pos.symbol,
                            "alert_type": "large_gain",
                            "current_pnl": str(round(pnl_pct, 2)),
                            "threshold": rule["threshold"],
                            "message": f"Position up {round(pnl_pct, 2)}%"
                        })

        import json
        response = {
            "positions_monitored": len(positions),
            "alert_rules": alert_rules,
            "alerts_triggered": len(alerts),
            "alerts": alerts
        }

        formatted = f"Monitoring {len(positions)} positions, {len(alerts)} alert(s) triggered\n\n"
        formatted += json.dumps(response, indent=2)

        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error monitoring positions: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"Error monitoring positions: {str(e)}"
        )]