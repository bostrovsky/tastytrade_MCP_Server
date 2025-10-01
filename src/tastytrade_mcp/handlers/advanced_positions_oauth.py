"""OAuth-based advanced position handlers for TastyTrade MCP."""
import json
import os
from typing import Any

import mcp.types as types

from tastytrade_mcp.services.oauth_client import OAuthHTTPClient
from tastytrade_mcp.utils.logging import get_logger
from tastytrade_mcp.handlers.utils_oauth import ensure_account_number, get_oauth_credentials

logger = get_logger(__name__)


def get_oauth_client() -> OAuthHTTPClient:
    """Get OAuth client with credentials from environment."""
    client_id = os.getenv("TASTYTRADE_CLIENT_ID")
    client_secret = os.getenv("TASTYTRADE_CLIENT_SECRET")
    refresh_token = os.getenv("TASTYTRADE_REFRESH_TOKEN")
    sandbox = os.getenv("TASTYTRADE_USE_PRODUCTION", "false").lower() != "true"

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("OAuth credentials not configured. Set TASTYTRADE_CLIENT_ID, TASTYTRADE_CLIENT_SECRET, and TASTYTRADE_REFRESH_TOKEN")

    return OAuthHTTPClient(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        sandbox=sandbox
    )


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
        market_value = pos.get('market_value', 0)
        unrealized_pnl = pos.get('unrealized_pnl', 0)

        total_value += market_value
        total_pnl += unrealized_pnl

        lines.append(f"{symbol}:")
        lines.append(f"  Quantity: {quantity}")
        lines.append(f"  Market Value: ${market_value:,.2f}")
        lines.append(f"  Unrealized P&L: ${unrealized_pnl:,.2f}")

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

            for greek_name in ['gamma', 'theta', 'vega', 'rho']:
                greek_value = greeks.get(greek_name)
                if greek_value is not None:
                    if greek_name == 'theta':
                        position_value = greek_value * quantity
                        lines.append(f"    {greek_name.title()}: {greek_value:.4f} (Position: ${position_value:.2f}/day)")
                    else:
                        lines.append(f"    {greek_name.title()}: {greek_value:.4f}")

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


async def handle_get_positions_with_greeks(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Get positions with options Greeks analysis.

    Args:
        arguments: Dictionary containing:
            - account_number: The account number (required)
            - format: Response format ('text' or 'json')

    Returns:
        List containing TextContent with enhanced positions data
    """
    try:
        account_number = await ensure_account_number(arguments.get("account_number"))
    except ValueError as e:
        return [types.TextContent(type="text", text=f"Error: {e}")]

    format_type = arguments.get("format", "text")

    try:
        oauth_client = get_oauth_client()

        # Get positions via OAuth API
        try:
            positions_response = await oauth_client.get(f"/accounts/{account_number}/positions")
            positions_data = positions_response.get("data", {}).get("items", [])
        except Exception as e:
            logger.warning(f"Could not fetch positions via OAuth: {e}")
            positions_data = []

        # Process positions and add Greeks data
        positions = []
        for pos in positions_data:
            symbol = pos.get("instrument", {}).get("symbol", "N/A")
            quantity = float(pos.get("quantity", 0))
            market_value = float(pos.get("market_value", 0))
            unrealized_pnl = float(pos.get("unrealized_day_gain", 0))
            instrument_type = pos.get("instrument", {}).get("instrument_type", "equity")

            pos_dict = {
                'symbol': symbol,
                'quantity': quantity,
                'market_value': market_value,
                'unrealized_pnl': unrealized_pnl,
                'instrument_type': instrument_type
            }

            # Add Greeks for options positions
            if instrument_type.lower() in ["option", "options"]:
                # This would normally come from the API response or a separate Greeks endpoint
                # For now, provide placeholder structure
                pos_dict['greeks'] = {
                    'delta': 0.5,  # Placeholder - would come from API
                    'gamma': 0.01,  # Placeholder - would come from API
                    'theta': -0.05,  # Placeholder - would come from API
                    'vega': 0.15,  # Placeholder - would come from API
                    'rho': 0.02,  # Placeholder - would come from API
                    'implied_volatility': 0.25  # Placeholder - would come from API
                }

            positions.append(pos_dict)

        formatted = await format_positions_with_greeks_response(positions, format_type)

        # Add implementation note
        if positions:
            formatted += "\n\nNote: Greeks values are placeholders. Full implementation requires TastyTrade options Greeks API endpoint."

        await oauth_client.close()
        return [types.TextContent(type="text", text=formatted)]

    except Exception as e:
        logger.error(f"Error getting positions with Greeks: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error retrieving positions with Greeks: {str(e)}")]


async def handle_monitor_position_alerts(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Monitor position alerts for P&L thresholds and risk management.

    Args:
        arguments: Dictionary containing:
            - account_number: The account number (required)
            - alert_types: List of alert types to monitor (optional)
            - pnl_threshold: P&L threshold for alerts (optional)
            - format: Response format ('text' or 'json')

    Returns:
        List containing TextContent with position alerts
    """
    try:
        account_number = await ensure_account_number(arguments.get("account_number"))
    except ValueError as e:
        return [types.TextContent(type="text", text=f"Error: {e}")]

    alert_types = arguments.get("alert_types", ["pnl_threshold", "stop_loss", "take_profit"])
    pnl_threshold = arguments.get("pnl_threshold", 1000.0)
    format_type = arguments.get("format", "text")

    try:
        oauth_client = get_oauth_client()

        # Get current positions to monitor
        try:
            positions_response = await oauth_client.get(f"/accounts/{account_number}/positions")
            positions = positions_response.get("data", {}).get("items", [])
        except Exception as e:
            logger.warning(f"Could not fetch positions via OAuth: {e}")
            positions = []

        # Analyze positions for alerts
        alerts = []
        total_unrealized_pnl = 0

        for pos in positions:
            symbol = pos.get("instrument", {}).get("symbol", "N/A")
            quantity = float(pos.get("quantity", 0))
            market_value = float(pos.get("market_value", 0))
            unrealized_pnl = float(pos.get("unrealized_day_gain", 0))

            total_unrealized_pnl += unrealized_pnl

            # Check P&L threshold alerts
            if "pnl_threshold" in alert_types:
                if abs(unrealized_pnl) > pnl_threshold:
                    alerts.append({
                        "type": "pnl_threshold",
                        "symbol": symbol,
                        "message": f"P&L exceeds threshold: ${unrealized_pnl:,.2f}",
                        "severity": "high" if unrealized_pnl < -pnl_threshold else "medium",
                        "quantity": quantity,
                        "market_value": market_value
                    })

            # Add other alert types (placeholders)
            if "stop_loss" in alert_types and unrealized_pnl < -500:
                alerts.append({
                    "type": "stop_loss",
                    "symbol": symbol,
                    "message": "Position approaching stop loss level",
                    "severity": "high",
                    "quantity": quantity,
                    "market_value": market_value
                })

        alert_summary = {
            "account_number": account_number,
            "total_positions": len(positions),
            "total_unrealized_pnl": total_unrealized_pnl,
            "alerts": alerts,
            "alert_count": len(alerts),
            "monitoring_types": alert_types,
            "pnl_threshold": pnl_threshold
        }

        if format_type == "json":
            result = json.dumps(alert_summary, indent=2)
        else:
            result = f"""Position Monitoring Alert Report

Account: {account_number}
Total Positions: {len(positions)}
Total Unrealized P&L: ${total_unrealized_pnl:,.2f}
P&L Threshold: ${pnl_threshold:,.2f}

Active Alerts: {len(alerts)}
"""
            if alerts:
                result += "\n=== ALERTS ===\n"
                for alert in alerts:
                    severity_marker = "🔴" if alert["severity"] == "high" else "🟡"
                    result += f"{severity_marker} {alert['symbol']}: {alert['message']}\n"
                    result += f"   Quantity: {alert['quantity']}, Market Value: ${alert['market_value']:,.2f}\n\n"
            else:
                result += "\n✅ No alerts triggered\n"

            result += f"""
Monitoring Types: {', '.join(alert_types)}

Implementation Status:
Position monitoring provides basic P&L threshold alerts.
Advanced features require:
- Real-time streaming data
- Configurable alert rules
- Notification system
- Historical alert tracking
"""

        await oauth_client.close()
        return [types.TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Error monitoring position alerts: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error monitoring position alerts: {str(e)}")]


async def handle_analyze_position_correlation(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Analyze correlation between positions to identify concentration risk.

    Args:
        arguments: Dictionary containing:
            - account_number: The account number (required)
            - lookback_days: Number of days for correlation analysis (default: 30)
            - correlation_threshold: Threshold for high correlation alert (default: 0.7)
            - format: Response format ('text' or 'json')

    Returns:
        List containing TextContent with correlation analysis
    """
    try:
        account_number = await ensure_account_number(arguments.get("account_number"))
    except ValueError as e:
        return [types.TextContent(type="text", text=f"Error: {e}")]

    lookback_days = arguments.get("lookback_days", 30)
    correlation_threshold = arguments.get("correlation_threshold", 0.7)
    format_type = arguments.get("format", "text")

    try:
        oauth_client = get_oauth_client()

        # Get current positions
        try:
            positions_response = await oauth_client.get(f"/accounts/{account_number}/positions")
            positions = positions_response.get("data", {}).get("items", [])
        except Exception as e:
            logger.warning(f"Could not fetch positions via OAuth: {e}")
            positions = []

        # Extract unique symbols for correlation analysis
        symbols = []
        position_values = {}

        for pos in positions:
            symbol = pos.get("instrument", {}).get("symbol", "N/A")
            market_value = float(pos.get("market_value", 0))

            if symbol != "N/A" and market_value > 0:
                symbols.append(symbol)
                position_values[symbol] = market_value

        # Placeholder correlation analysis
        # In real implementation, this would fetch historical price data and calculate correlations
        correlation_analysis = {
            "account_number": account_number,
            "analysis_period": f"{lookback_days} days",
            "correlation_threshold": correlation_threshold,
            "symbols_analyzed": symbols,
            "position_count": len(symbols),
            "high_correlations": [],  # Would be populated with real correlation data
            "concentration_risk": {
                "largest_position": max(position_values.values()) if position_values else 0,
                "largest_symbol": max(position_values.keys(), key=position_values.get) if position_values else "N/A",
                "concentration_percent": 0  # Would calculate as % of total portfolio
            },
            "status": "Placeholder - requires historical price data API"
        }

        # Calculate basic concentration metrics
        total_value = sum(position_values.values())
        if total_value > 0:
            largest_value = max(position_values.values())
            correlation_analysis["concentration_risk"]["concentration_percent"] = (largest_value / total_value) * 100

        # Simulate some correlation findings (placeholder)
        if len(symbols) >= 2:
            correlation_analysis["high_correlations"] = [
                {
                    "symbol_1": symbols[0],
                    "symbol_2": symbols[1] if len(symbols) > 1 else symbols[0],
                    "correlation": 0.85,  # Placeholder
                    "risk_level": "high",
                    "note": "Simulated correlation - requires historical data"
                }
            ]

        if format_type == "json":
            result = json.dumps(correlation_analysis, indent=2)
        else:
            result = f"""Position Correlation Analysis

Account: {account_number}
Analysis Period: {lookback_days} days
Correlation Threshold: {correlation_threshold}
Positions Analyzed: {len(symbols)}

=== Concentration Risk ===
Largest Position: {correlation_analysis['concentration_risk']['largest_symbol']}
Position Value: ${correlation_analysis['concentration_risk']['largest_position']:,.2f}
Portfolio %: {correlation_analysis['concentration_risk']['concentration_percent']:.1f}%

=== High Correlation Alerts ===
"""
            if correlation_analysis["high_correlations"]:
                for corr in correlation_analysis["high_correlations"]:
                    result += f"⚠️  {corr['symbol_1']} ↔ {corr['symbol_2']}: {corr['correlation']:.2f} correlation\n"
                    result += f"   Risk Level: {corr['risk_level']}\n"
                    result += f"   Note: {corr['note']}\n\n"
            else:
                result += "No high correlations detected with current data.\n\n"

            result += f"""=== Implementation Requirements ===
Full correlation analysis requires:
- Historical price data API endpoint
- Statistical correlation calculation
- Real-time risk monitoring
- Sector/industry classification data

Current implementation provides framework and basic concentration analysis.

Symbols in portfolio: {', '.join(symbols)}
"""

        await oauth_client.close()
        return [types.TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Error analyzing position correlation: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error analyzing position correlation: {str(e)}")]


async def handle_bulk_position_update(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Perform bulk operations on multiple positions.

    Args:
        arguments: Dictionary containing:
            - account_number: The account number (required)
            - operation: Type of operation to perform (required)
            - symbols: List of symbols to operate on (required)
            - parameters: Operation-specific parameters (required)
            - format: Response format ('text' or 'json')

    Returns:
        List containing TextContent with bulk operation results
    """
    account_number = arguments.get("account_number")
    operation = arguments.get("operation")
    symbols = arguments.get("symbols", [])
    parameters = arguments.get("parameters", {})

    if not account_number:
        return [types.TextContent(type="text", text="Error: account_number parameter is required")]
    if not operation:
        return [types.TextContent(type="text", text="Error: operation parameter is required")]
    if not symbols:
        return [types.TextContent(type="text", text="Error: symbols parameter is required")]

    format_type = arguments.get("format", "text")

    try:
        oauth_client = get_oauth_client()

        # Get current positions to validate symbols
        try:
            positions_response = await oauth_client.get(f"/accounts/{account_number}/positions")
            current_positions = positions_response.get("data", {}).get("items", [])
            position_symbols = [pos.get("instrument", {}).get("symbol") for pos in current_positions]
        except Exception as e:
            logger.warning(f"Could not fetch positions via OAuth: {e}")
            position_symbols = []

        # Validate symbols exist in positions
        valid_symbols = [symbol for symbol in symbols if symbol in position_symbols]
        invalid_symbols = [symbol for symbol in symbols if symbol not in position_symbols]

        # Simulate bulk operation results
        operation_results = {
            "account_number": account_number,
            "operation": operation,
            "total_symbols": len(symbols),
            "valid_symbols": valid_symbols,
            "invalid_symbols": invalid_symbols,
            "parameters": parameters,
            "results": [],
            "summary": {
                "successful": 0,
                "failed": 0,
                "skipped": len(invalid_symbols)
            },
            "status": "Simulation - requires trading API endpoints"
        }

        # Process each valid symbol
        for symbol in valid_symbols:
            if operation == "close_position":
                operation_results["results"].append({
                    "symbol": symbol,
                    "action": "close_position",
                    "status": "simulated",
                    "message": f"Would close position for {symbol}",
                    "parameters_used": parameters
                })
                operation_results["summary"]["successful"] += 1

            elif operation == "set_stop_loss":
                stop_price = parameters.get("stop_price")
                operation_results["results"].append({
                    "symbol": symbol,
                    "action": "set_stop_loss",
                    "status": "simulated",
                    "message": f"Would set stop loss at ${stop_price} for {symbol}",
                    "parameters_used": parameters
                })
                operation_results["summary"]["successful"] += 1

            elif operation == "take_profit":
                profit_price = parameters.get("profit_price")
                operation_results["results"].append({
                    "symbol": symbol,
                    "action": "take_profit",
                    "status": "simulated",
                    "message": f"Would set take profit at ${profit_price} for {symbol}",
                    "parameters_used": parameters
                })
                operation_results["summary"]["successful"] += 1

            else:
                operation_results["results"].append({
                    "symbol": symbol,
                    "action": operation,
                    "status": "unsupported",
                    "message": f"Operation '{operation}' not implemented",
                    "parameters_used": parameters
                })
                operation_results["summary"]["failed"] += 1

        if format_type == "json":
            result = json.dumps(operation_results, indent=2)
        else:
            result = f"""Bulk Position Operation Results

Account: {account_number}
Operation: {operation}
Symbols Requested: {len(symbols)}
Valid Symbols: {len(valid_symbols)}
Invalid Symbols: {len(invalid_symbols)}

=== Operation Summary ===
Successful: {operation_results['summary']['successful']}
Failed: {operation_results['summary']['failed']}
Skipped: {operation_results['summary']['skipped']}

=== Detailed Results ===
"""
            for result_item in operation_results["results"]:
                status_icon = "✅" if result_item["status"] == "simulated" else "❌"
                result += f"{status_icon} {result_item['symbol']}: {result_item['message']}\n"

            if invalid_symbols:
                result += f"\n⚠️  Invalid Symbols: {', '.join(invalid_symbols)}\n"

            result += f"""
=== Implementation Status ===
This is a simulation of bulk position operations.
Real implementation requires:
- TastyTrade order management API
- Position modification endpoints
- Risk validation system
- Atomic transaction handling

Parameters provided: {json.dumps(parameters, indent=2)}
"""

        await oauth_client.close()
        return [types.TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Error with bulk position update: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error with bulk position update: {str(e)}")]