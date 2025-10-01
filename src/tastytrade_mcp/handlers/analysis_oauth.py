"""OAuth-based analysis handlers for TastyTrade MCP."""
import json
import os
from datetime import datetime, date
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


async def handle_analyze_options_strategy(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Analyze an options strategy with risk metrics and Greeks.

    Args:
        arguments: Dictionary containing:
            - underlying_symbol: The underlying symbol (required)
            - underlying_price: Current price of underlying (required)
            - legs: List of option legs (required)
            - format: Response format ('text' or 'json')

    Returns:
        List containing TextContent with strategy analysis
    """
    # Validate required parameters
    underlying_symbol = arguments.get("underlying_symbol")
    underlying_price = arguments.get("underlying_price")
    legs = arguments.get("legs", [])

    if not all([underlying_symbol, underlying_price, legs]):
        return [
            types.TextContent(
                type="text",
                text="Error: underlying_symbol, underlying_price, and legs are required"
            )
        ]

    try:
        oauth_client = get_oauth_client()
        format_type = arguments.get("format", "text")

        # This is a complex analysis that would require:
        # 1. Real-time options chain data
        # 2. Greeks calculation
        # 3. Risk analysis algorithms
        # For now, provide a structured placeholder

        # Simulate strategy analysis
        strategy_analysis = {
            "strategy": "Complex Options Strategy",
            "underlying_symbol": underlying_symbol,
            "underlying_price": float(underlying_price),
            "legs_count": len(legs),
            "analysis": {
                "max_profit": "To be calculated with real options data",
                "max_loss": "To be calculated with real options data",
                "breakeven_points": "To be calculated with real options data",
                "greeks": {
                    "total_delta": "Requires options chain API",
                    "total_gamma": "Requires options chain API",
                    "total_theta": "Requires options chain API",
                    "total_vega": "Requires options chain API"
                }
            },
            "legs": legs,
            "status": "Analysis placeholder - requires options chain API endpoint"
        }

        if format_type == "json":
            result = json.dumps(strategy_analysis, indent=2)
        else:
            result = f"""Options Strategy Analysis:

Strategy: Complex Options Strategy
Underlying: {underlying_symbol} @ ${underlying_price}
Number of Legs: {len(legs)}

Implementation Status:
This is a placeholder implementation. Full options strategy analysis requires:
- Real-time options chain data from TastyTrade API
- Market data for Greeks calculation
- Risk analysis algorithms

Current legs provided:
"""
            for i, leg in enumerate(legs, 1):
                result += f"  {i}. {leg.get('side', 'N/A')} {leg.get('quantity', 'N/A')} {leg.get('option_type', 'N/A')} @ ${leg.get('strike_price', 'N/A')} (exp: {leg.get('expiration_date', 'N/A')})\n"

            result += f"\nTo implement: Need TastyTrade options chain API endpoint and Greeks calculation service."

        await oauth_client.close()
        return [types.TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Failed to analyze options strategy: {e}", exc_info=True)
        return [
            types.TextContent(
                type="text",
                text=f"Error analyzing options strategy: {str(e)}"
            )
        ]


async def handle_suggest_rebalancing(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Suggest portfolio rebalancing based on target allocations.

    Args:
        arguments: Dictionary containing:
            - account_number: The account number (required)
            - target_allocations: Dictionary of symbol -> target percentage (required)
            - rebalance_threshold: Deviation threshold to trigger rebalancing (default: 5.0%)
            - format: Response format ('text' or 'json')

    Returns:
        List containing TextContent with rebalancing suggestions
    """
    account_number = arguments.get("account_number")
    target_allocations = arguments.get("target_allocations", {})
    rebalance_threshold = arguments.get("rebalance_threshold", 5.0)

    if not account_number:
        return [types.TextContent(type="text", text="Error: account_number parameter is required")]
    if not target_allocations:
        return [types.TextContent(type="text", text="Error: target_allocations parameter is required")]

    try:
        oauth_client = get_oauth_client()
        format_type = arguments.get("format", "text")

        # Get current positions via OAuth API
        try:
            # This would call the actual positions endpoint
            positions_response = await oauth_client.get(f"/accounts/{account_number}/positions")
            positions = positions_response.get("data", {}).get("items", [])
        except Exception as e:
            logger.warning(f"Could not fetch positions via OAuth: {e}")
            positions = []

        # Calculate rebalancing suggestions
        rebalancing_analysis = {
            "account_number": account_number,
            "target_allocations": target_allocations,
            "rebalance_threshold": rebalance_threshold,
            "current_positions_count": len(positions),
            "suggestions": [],
            "status": "Analysis requires current market values and position details"
        }

        total_target = sum(target_allocations.values())
        if abs(total_target - 100.0) > 0.01:
            rebalancing_analysis["warning"] = f"Target allocations sum to {total_target:.1f}%, not 100%"

        # Provide basic rebalancing framework
        for symbol, target_pct in target_allocations.items():
            rebalancing_analysis["suggestions"].append({
                "symbol": symbol,
                "target_allocation": f"{target_pct:.1f}%",
                "action": "Requires position value calculation",
                "amount": "To be calculated with market data"
            })

        if format_type == "json":
            result = json.dumps(rebalancing_analysis, indent=2)
        else:
            result = f"""Portfolio Rebalancing Analysis:

Account: {account_number}
Rebalance Threshold: {rebalance_threshold:.1f}%
Current Positions: {len(positions)}

Target Allocations:
"""
            if "warning" in rebalancing_analysis:
                result += f"⚠️  Warning: {rebalancing_analysis['warning']}\n\n"

            for symbol, target_pct in target_allocations.items():
                result += f"• {symbol}: {target_pct:.1f}%\n"

            result += f"""
Implementation Status:
Full rebalancing analysis requires:
- Current position market values
- Real-time price data for calculations
- Trading cost estimates

This placeholder provides the framework for rebalancing logic.
"""

        await oauth_client.close()
        return [types.TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Error suggesting rebalancing: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error suggesting rebalancing: {str(e)}")]


async def handle_analyze_portfolio(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Analyze portfolio composition and risk metrics.

    Args:
        arguments: Dictionary containing:
            - account_number: The account number (required)
            - format: Response format ('text' or 'json')

    Returns:
        List containing TextContent with portfolio analysis
    """
    try:
        account_number = await ensure_account_number(arguments.get("account_number"))
    except ValueError as e:
        return [types.TextContent(type="text", text=f"Error: {e}")]

    try:
        oauth_client = get_oauth_client()
        format_type = arguments.get("format", "text")

        # Get account data via OAuth API
        try:
            # Get positions
            positions_response = await oauth_client.get(f"/accounts/{account_number}/positions")
            positions = positions_response.get("data", {}).get("items", [])

            # Get balances
            balances_response = await oauth_client.get(f"/accounts/{account_number}/balances")
            balances = balances_response.get("data", {})
        except Exception as e:
            logger.warning(f"Could not fetch account data via OAuth: {e}")
            positions = []
            balances = {}

        # Perform portfolio analysis
        total_market_value = 0
        total_unrealized_pnl = 0
        position_count = len(positions)
        option_count = 0
        asset_allocation = {}
        underlying_analysis = {}

        for pos in positions:
            # Extract position data (structure depends on actual API response)
            symbol = pos.get("instrument", {}).get("symbol", "N/A")
            quantity = float(pos.get("quantity", 0))
            market_value = float(pos.get("market_value", 0))
            unrealized_pnl = float(pos.get("unrealized_day_gain", 0))
            instrument_type = pos.get("instrument", {}).get("instrument_type", "equity")

            total_market_value += market_value
            total_unrealized_pnl += unrealized_pnl

            # Asset allocation
            asset_allocation[instrument_type] = asset_allocation.get(instrument_type, 0) + market_value

            # Count options
            if instrument_type.lower() in ["option", "options"]:
                option_count += 1

            # Underlying analysis
            underlying = pos.get("instrument", {}).get("underlying_symbol", symbol)
            if underlying not in underlying_analysis:
                underlying_analysis[underlying] = {
                    "total_market_value": 0,
                    "position_count": 0,
                    "total_delta": 0
                }
            underlying_analysis[underlying]["total_market_value"] += market_value
            underlying_analysis[underlying]["position_count"] += 1

        analysis = {
            "account_number": account_number,
            "summary": {
                "total_market_value": total_market_value,
                "total_unrealized_pnl": total_unrealized_pnl,
                "position_count": position_count,
                "option_positions": option_count,
                "cash_balance": balances.get("cash_balance", 0)
            },
            "asset_allocation": {
                "total_value": total_market_value,
                "by_asset_type": asset_allocation
            },
            "underlying_analysis": underlying_analysis,
            "risk_metrics": {
                "concentration_risk": "Requires additional analysis",
                "portfolio_beta": "Requires market data",
                "var_analysis": "Requires historical data"
            }
        }

        if format_type == "json":
            result = json.dumps(analysis, indent=2)
        else:
            result = f"""Portfolio Analysis Report

Account: {account_number}

=== Portfolio Summary ===
Total Market Value: ${total_market_value:,.2f}
Total Unrealized P&L: ${total_unrealized_pnl:,.2f}
Cash Balance: ${balances.get('cash_balance', 0):,.2f}
Position Count: {position_count}
Option Positions: {option_count}

=== Asset Allocation ===
"""
            if total_market_value > 0:
                for asset_type, amount in asset_allocation.items():
                    percentage = (amount / total_market_value) * 100
                    result += f"{asset_type.title()}: ${amount:,.2f} ({percentage:.1f}%)\n"
            else:
                result += "No positions with market value\n"

            result += f"""
=== By Underlying Symbol ===
"""
            for symbol, data in underlying_analysis.items():
                result += f"{symbol}: {data['position_count']} positions, ${data['total_market_value']:,.2f}\n"

            result += f"""
=== Implementation Notes ===
Full portfolio analysis requires:
- Real-time Greeks for options positions
- Historical correlation data
- Risk metrics calculation
- Beta and VaR analysis

This OAuth implementation provides the foundation for comprehensive portfolio analysis.
"""

        await oauth_client.close()
        return [types.TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"Error analyzing portfolio: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error analyzing portfolio: {str(e)}")]