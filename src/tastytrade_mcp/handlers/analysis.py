"""Analysis handlers for TastyTrade MCP."""
import json
from datetime import datetime, date
from typing import Any

import mcp.types as types
from tastytrade import Account

from tastytrade_mcp.handlers.handler_adapter import HandlerAdapter
from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.services.options import (
    StrategyRecognizer,
    GreeksCalculator,
    OptionRiskAnalyzer
)
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()
adapter = HandlerAdapter(use_database=settings.use_database_mode)


async def handle_analyze_options_strategy(arguments: dict[str, Any]) -> list[types.TextContent]:
    """Analyze an options strategy with risk metrics and Greeks.

    Args:
        arguments: Dictionary containing:
            - user_id: User ID (required for database mode)
            - underlying_symbol: The underlying symbol (required)
            - underlying_price: Current price of underlying (required)
            - legs: List of option legs (required)
            - format: Response format ('text' or 'json')

    Returns:
        List containing TextContent with strategy analysis
    """
    user_id = arguments.get("user_id", "default")

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
        # Get session through adapter
        session = await adapter.get_session(user_id)

        # Check if we need advanced analysis features
        if settings.use_database_mode:
            return [types.TextContent(
                type="text",
                text="Advanced options analysis with real market data requires database mode (not yet implemented)"
            )]

        # Initialize analyzers
        strategy_recognizer = StrategyRecognizer()
        greeks_calculator = GreeksCalculator()
        risk_analyzer = OptionRiskAnalyzer()

        # Identify strategy
        strategy, strategy_name = strategy_recognizer.identify_strategy(legs)

        # Calculate aggregated Greeks
        total_greeks = {}
        for leg in legs:
            # Parse expiration date
            exp_date = datetime.strptime(leg['expiration_date'], '%Y-%m-%d').date()
            days_to_expiry = (exp_date - date.today()).days

            # Calculate Greeks for this leg
            leg_greeks = greeks_calculator.calculate_greeks(
                spot_price=float(underlying_price),
                strike_price=float(leg['strike_price']),
                time_to_expiry=days_to_expiry / 365.0,
                risk_free_rate=0.05,  # Risk-free rate
                implied_volatility=0.30,  # Implied volatility (would normally come from market data)
                option_type=leg['option_type']
            )

            # Aggregate based on position
            multiplier = leg['quantity'] * (1 if leg['side'] == 'buy' else -1)
            for greek, value in leg_greeks.items():
                total_greeks[greek] = total_greeks.get(greek, 0) + value * multiplier

        # Calculate risk metrics
        risk_metrics = risk_analyzer.assess_strategy_risk(
            legs, float(underlying_price), account_balance=100000.0
        )

        # Format response
        format_type = arguments.get("format", "text")

        if format_type == "json":
            result = json.dumps({
                "strategy": strategy_name,
                "underlying_symbol": underlying_symbol,
                "underlying_price": underlying_price,
                "greeks": {k: round(v, 4) for k, v in total_greeks.items()},
                "risk_metrics": {
                    "max_profit": risk_metrics.get('max_profit'),
                    "max_loss": risk_metrics.get('max_loss'),
                    "breakeven_points": risk_metrics.get('breakeven_points', [])
                }
            }, indent=2, default=str)
        else:
            result = f"""Options Strategy Analysis:

Strategy: {strategy_name}
Underlying: {underlying_symbol} @ ${underlying_price}

Risk/Reward Profile:
  Max Profit: ${risk_metrics.get('max_profit', 'Unlimited')}
  Max Loss: ${risk_metrics.get('max_loss', 'Unlimited')}
  Breakeven Points: {', '.join([f"${bp:.2f}" for bp in risk_metrics.get('breakeven_points', [])])}

Position Greeks:
  Delta: {total_greeks.get('delta', 0):.4f}
  Gamma: {total_greeks.get('gamma', 0):.4f}
  Theta: {total_greeks.get('theta', 0):.4f}
  Vega: {total_greeks.get('vega', 0):.4f}
  Rho: {total_greeks.get('rho', 0):.4f}

Legs:
"""
            for i, leg in enumerate(legs, 1):
                result += f"  {i}. {leg['side'].upper()} {leg['quantity']} {leg['option_type'].upper()} @ ${leg['strike_price']} (exp: {leg['expiration_date']})\n"
                result += f"     Premium: ${leg['premium']}/contract\n"

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
            - user_id: The user ID (required)
            - account_number: The account number (optional, auto-detected if not provided)
            - target_allocations: Dictionary of symbol -> target percentage (required)
            - rebalance_threshold: Deviation threshold to trigger rebalancing (default: 5.0%)

    Returns:
        List containing TextContent with rebalancing suggestions
    """
    user_id = arguments.get("user_id", "default")
    account_number = arguments.get("account_number")
    target_allocations = arguments.get("target_allocations", {})
    rebalance_threshold = arguments.get("rebalance_threshold", 5.0)

    if not target_allocations:
        return [types.TextContent(type="text", text="Error: target_allocations parameter is required")]

    try:
        # Get session through adapter
        session = await adapter.get_session(user_id)

        # Auto-detect account number if not provided
        if not account_number:
            account_number = await adapter.get_account_number(user_id)

        # Check if we need advanced rebalancing features
        if settings.use_database_mode:
            return [types.TextContent(
                type="text",
                text="Advanced portfolio rebalancing with position tracking requires database mode (not yet implemented)"
            )]

        # For simple mode, provide basic rebalancing guidance
        accounts = Account.get(session)
        if not accounts:
            return [types.TextContent(type="text", text="No accounts found for authenticated user.")]

        # Find the target account
        target_account = None
        for account in accounts:
            if account.account_number == account_number:
                target_account = account
                break

        if not target_account:
            return [types.TextContent(type="text", text=f"Account {account_number} not found.")]

        # Basic rebalancing analysis (simplified version)
        result_text = "Portfolio Rebalancing Analysis:\n\n"
        result_text += f"Account: {account_number}\n"
        result_text += f"Target Allocations:\n"

        total_target = sum(target_allocations.values())
        if abs(total_target - 100.0) > 0.01:
            result_text += f"⚠️  Warning: Target allocations sum to {total_target:.1f}%, not 100%\n\n"

        for symbol, target_pct in target_allocations.items():
            result_text += f"• {symbol}: {target_pct:.1f}%\n"

        result_text += f"\nRebalance Threshold: {rebalance_threshold:.1f}%\n\n"
        result_text += "Note: For detailed position analysis and specific rebalancing actions, "
        result_text += "advanced portfolio analysis features are required (coming in database mode).\n\n"
        result_text += "Current implementation provides target allocation setup and basic validation."

        return [types.TextContent(type="text", text=result_text)]

    except Exception as e:
        logger.error(f"Error suggesting rebalancing: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error suggesting rebalancing: {str(e)}")]