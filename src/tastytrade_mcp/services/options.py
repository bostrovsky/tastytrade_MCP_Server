"""Options trading service with strategy validation and risk assessment."""
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import numpy as np
from scipy import stats
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tastytrade_mcp.models.options import (
    OptionType, OptionAction, OptionStrategy, OptionApprovalLevel,
    OptionOrder, OptionLeg, OptionRiskAssessment, OptionChainCache
)
from tastytrade_mcp.models.user import User
from tastytrade_mcp.services.tastytrade import TastyTradeService
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class StrategyRecognizer:
    """Recognizes common options strategies from legs."""

    @staticmethod
    def identify_strategy(legs: List[Dict[str, Any]]) -> Tuple[OptionStrategy, str]:
        """
        Identify the options strategy from leg configuration.

        Args:
            legs: List of option leg configurations

        Returns:
            Tuple of (strategy_type, strategy_name)
        """
        num_legs = len(legs)

        if num_legs == 1:
            return OptionStrategy.SINGLE, "Single Option"

        if num_legs == 2:
            return StrategyRecognizer._identify_two_leg_strategy(legs)

        if num_legs == 3:
            return StrategyRecognizer._identify_three_leg_strategy(legs)

        if num_legs == 4:
            return StrategyRecognizer._identify_four_leg_strategy(legs)

        return OptionStrategy.CUSTOM, f"Custom {num_legs}-Leg Strategy"

    @staticmethod
    def _identify_two_leg_strategy(legs: List[Dict]) -> Tuple[OptionStrategy, str]:
        """Identify two-leg strategies."""
        leg1, leg2 = legs[0], legs[1]

        # Same expiration
        if leg1['expiration_date'] == leg2['expiration_date']:
            # Same type (both calls or both puts)
            if leg1['option_type'] == leg2['option_type']:
                # Check if 'action' key exists, otherwise use 'side'
                leg1_action = leg1.get('action', leg1.get('side', ''))
                leg2_action = leg2.get('action', leg2.get('side', ''))

                if leg1_action != leg2_action:
                    # One buy, one sell - vertical spread
                    return OptionStrategy.VERTICAL_SPREAD, f"{leg1['option_type'].title()} Vertical Spread"

            # Different types (call and put)
            else:
                if leg1['strike_price'] == leg2['strike_price']:
                    # Same strike - straddle or synthetic
                    leg1_action = leg1.get('action', leg1.get('side', ''))
                    leg2_action = leg2.get('action', leg2.get('side', ''))

                    if leg1_action == leg2_action:
                        action = "Long" if 'buy' in leg1_action.lower() else "Short"
                        return OptionStrategy.STRADDLE, f"{action} Straddle"

        # Different expiration - calendar spread
        elif leg1['strike_price'] == leg2['strike_price']:
            return OptionStrategy.CALENDAR_SPREAD, "Calendar Spread"

        # Different expiration and strike - diagonal
        else:
            return OptionStrategy.DIAGONAL_SPREAD, "Diagonal Spread"

        return OptionStrategy.CUSTOM, "Custom 2-Leg Strategy"

    @staticmethod
    def _identify_three_leg_strategy(legs: List[Dict]) -> Tuple[OptionStrategy, str]:
        """Identify three-leg strategies."""
        # Check for butterfly
        strikes = sorted([leg['strike_price'] for leg in legs])
        if strikes[1] - strikes[0] == strikes[2] - strikes[1]:
            # Equal spacing - likely butterfly
            return OptionStrategy.BUTTERFLY, "Butterfly Spread"

        return OptionStrategy.CUSTOM, "Custom 3-Leg Strategy"

    @staticmethod
    def _identify_four_leg_strategy(legs: List[Dict]) -> Tuple[OptionStrategy, str]:
        """Identify four-leg strategies."""
        calls = [leg for leg in legs if leg['option_type'] == OptionType.CALL]
        puts = [leg for leg in legs if leg['option_type'] == OptionType.PUT]

        if len(calls) == 2 and len(puts) == 2:
            # Iron condor or iron butterfly
            call_strikes = sorted([c['strike_price'] for c in calls])
            put_strikes = sorted([p['strike_price'] for p in puts])

            if put_strikes[1] < call_strikes[0]:
                # Proper iron condor/butterfly structure
                if call_strikes[0] == put_strikes[1]:
                    return OptionStrategy.IRON_BUTTERFLY, "Iron Butterfly"
                else:
                    return OptionStrategy.IRON_CONDOR, "Iron Condor"

        return OptionStrategy.CUSTOM, "Custom 4-Leg Strategy"


class GreeksCalculator:
    """Calculate options Greeks using Black-Scholes model."""

    @staticmethod
    def calculate_greeks(
        spot_price: float,
        strike_price: float,
        time_to_expiry: float,
        risk_free_rate: float,
        implied_volatility: float,
        option_type: OptionType,
        dividend_yield: float = 0.0
    ) -> Dict[str, float]:
        """
        Calculate option Greeks using Black-Scholes model.

        Args:
            spot_price: Current price of underlying
            strike_price: Option strike price
            time_to_expiry: Time to expiration in years
            risk_free_rate: Risk-free interest rate
            implied_volatility: Implied volatility (annualized)
            option_type: CALL or PUT
            dividend_yield: Dividend yield (default 0)

        Returns:
            Dictionary with delta, gamma, theta, vega, rho
        """
        S = spot_price
        K = strike_price
        T = max(time_to_expiry, 1/365)  # Minimum 1 day
        r = risk_free_rate
        sigma = implied_volatility
        q = dividend_yield

        # Calculate d1 and d2
        d1 = (np.log(S/K) + (r - q + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        d2 = d1 - sigma*np.sqrt(T)

        # Calculate Greeks based on option type
        if option_type == OptionType.CALL:
            delta = np.exp(-q*T) * stats.norm.cdf(d1)
            theta = (-S*stats.norm.pdf(d1)*sigma*np.exp(-q*T)/(2*np.sqrt(T))
                     - r*K*np.exp(-r*T)*stats.norm.cdf(d2)
                     + q*S*np.exp(-q*T)*stats.norm.cdf(d1)) / 365
            rho = K*T*np.exp(-r*T)*stats.norm.cdf(d2) / 100
        else:  # PUT
            delta = -np.exp(-q*T) * stats.norm.cdf(-d1)
            theta = (-S*stats.norm.pdf(d1)*sigma*np.exp(-q*T)/(2*np.sqrt(T))
                     + r*K*np.exp(-r*T)*stats.norm.cdf(-d2)
                     - q*S*np.exp(-q*T)*stats.norm.cdf(-d1)) / 365
            rho = -K*T*np.exp(-r*T)*stats.norm.cdf(-d2) / 100

        # Greeks that are the same for calls and puts
        gamma = stats.norm.pdf(d1)*np.exp(-q*T) / (S*sigma*np.sqrt(T))
        vega = S*stats.norm.pdf(d1)*np.sqrt(T)*np.exp(-q*T) / 100

        return {
            "delta": round(delta, 6),
            "gamma": round(gamma, 6),
            "theta": round(theta, 6),
            "vega": round(vega, 6),
            "rho": round(rho, 6)
        }


class OptionRiskAnalyzer:
    """Analyze risk for options strategies."""

    @staticmethod
    def assess_strategy_risk(
        legs: List[Dict[str, Any]],
        underlying_price: float,
        account_balance: float
    ) -> Dict[str, Any]:
        """
        Assess risk for an options strategy.

        Args:
            legs: List of option legs
            underlying_price: Current underlying price
            account_balance: Account balance for position sizing

        Returns:
            Risk assessment dictionary
        """
        # Calculate max loss and gain
        max_loss, max_gain = OptionRiskAnalyzer._calculate_max_profit_loss(legs, underlying_price)

        # Calculate breakeven points
        breakevens = OptionRiskAnalyzer._calculate_breakevens(legs, underlying_price)

        # Assess assignment risk
        assignment_risk = OptionRiskAnalyzer._assess_assignment_risk(legs, underlying_price)

        # Calculate required margin
        margin_req = OptionRiskAnalyzer._calculate_margin_requirement(legs, underlying_price)

        # Generate warnings
        warnings = OptionRiskAnalyzer._generate_warnings(
            legs, underlying_price, account_balance, margin_req
        )

        return {
            "max_loss": max_loss,
            "max_gain": max_gain,
            "breakeven_points": breakevens,
            "assignment_risk": assignment_risk,
            "margin_requirement": margin_req,
            "buying_power_effect": margin_req,
            "warnings": warnings,
            "risk_score": OptionRiskAnalyzer._calculate_risk_score(max_loss, account_balance)
        }

    @staticmethod
    def _calculate_max_profit_loss(legs: List[Dict], underlying: float) -> Tuple[float, float]:
        """Calculate maximum profit and loss for the strategy."""
        # Simplified calculation - in production, this would be more complex
        total_debit = 0
        total_credit = 0

        for leg in legs:
            quantity = leg['quantity']
            # Try to get premium, then limit_price, then default to 0
            price = leg.get('premium', leg.get('limit_price', 0))

            # Check for 'action' first, then 'side'
            action = leg.get('action', leg.get('side', '')).lower()

            if 'buy' in action:
                total_debit += quantity * price * 100  # Options are in 100-share lots
            else:
                total_credit += quantity * price * 100

        net = total_credit - total_debit

        # Basic max loss/gain calculation
        if net > 0:
            # Net credit strategy
            max_gain = net
            max_loss = float('inf')  # Needs more complex calculation

            # Limit max loss for defined risk strategies
            if len(legs) >= 2:
                max_loss = abs(net) * 2  # Simplified
        else:
            # Net debit strategy
            max_loss = abs(net)
            max_gain = float('inf')  # Needs more complex calculation

            # Limit max gain for defined risk strategies
            if len(legs) >= 2:
                max_gain = abs(net) * 3  # Simplified

        return max_loss, max_gain

    @staticmethod
    def _calculate_breakevens(legs: List[Dict], underlying: float) -> List[float]:
        """Calculate breakeven points for the strategy."""
        # Simplified - actual calculation depends on strategy type
        breakevens = []

        # For single options
        if len(legs) == 1:
            leg = legs[0]
            strike = leg['strike_price']
            premium = leg.get('limit_price', 0)

            if leg['option_type'] == OptionType.CALL:
                action = leg.get('action', leg.get('side', '')).lower()
                if 'buy' in action:
                    breakevens.append(strike + premium)
                else:
                    breakevens.append(strike - premium)
            else:  # PUT
                action = leg.get('action', leg.get('side', '')).lower()
                if 'buy' in action:
                    breakevens.append(strike - premium)
                else:
                    breakevens.append(strike + premium)

        # For spreads, more complex calculation needed
        elif len(legs) >= 2:
            strikes = [leg['strike_price'] for leg in legs]
            breakevens.append(sum(strikes) / len(strikes))  # Simplified

        return breakevens

    @staticmethod
    def _assess_assignment_risk(legs: List[Dict], underlying: float) -> str:
        """Assess early assignment risk."""
        risk_level = "LOW"

        for leg in legs:
            action = leg.get('action', leg.get('side', '')).lower()
            if 'sell' in action:
                # Short options have assignment risk
                strike = leg['strike_price']
                moneyness = (underlying - strike) / strike

                if leg['option_type'] == OptionType.CALL:
                    if moneyness > 0.02:  # ITM call
                        risk_level = "HIGH" if moneyness > 0.05 else "MEDIUM"
                else:  # PUT
                    if moneyness < -0.02:  # ITM put
                        risk_level = "HIGH" if moneyness < -0.05 else "MEDIUM"

        return risk_level

    @staticmethod
    def _calculate_margin_requirement(legs: List[Dict], underlying: float) -> float:
        """Calculate margin requirement for the strategy."""
        # Simplified margin calculation
        margin = 0

        for leg in legs:
            action = leg.get('action', leg.get('side', '')).lower()
            if 'sell' in action:
                # Short options require margin
                quantity = leg['quantity']
                strike = leg['strike_price']

                # Basic margin: 20% of underlying + option premium
                margin += quantity * 100 * underlying * 0.20

        return margin

    @staticmethod
    def _generate_warnings(
        legs: List[Dict],
        underlying: float,
        balance: float,
        margin: float
    ) -> List[Dict[str, str]]:
        """Generate risk warnings."""
        warnings = []

        # Check position size
        if margin > balance * 0.5:
            warnings.append({
                "type": "POSITION_SIZE",
                "message": "Position requires >50% of account balance",
                "severity": "HIGH"
            })

        # Check for high IV
        for leg in legs:
            iv = leg.get('implied_volatility', 0)
            if iv > 0.5:  # 50% IV
                warnings.append({
                    "type": "HIGH_IV",
                    "message": f"High implied volatility: {iv:.1%}",
                    "severity": "MEDIUM"
                })

        # Check time to expiration
        for leg in legs:
            expiry = leg.get('expiration_date')
            if expiry:
                # Parse expiry if it's a string
                if isinstance(expiry, str):
                    expiry = datetime.strptime(expiry, '%Y-%m-%d')
                elif not isinstance(expiry, datetime):
                    expiry = datetime.combine(expiry, datetime.min.time())

                days_to_expiry = (expiry - datetime.now()).days
                if days_to_expiry <= 7:
                    warnings.append({
                        "type": "NEAR_EXPIRY",
                        "message": f"Option expires in {days_to_expiry} days",
                        "severity": "HIGH"
                    })

        return warnings

    @staticmethod
    def _calculate_risk_score(max_loss: float, balance: float) -> float:
        """Calculate risk score from 0-100."""
        if balance <= 0:
            return 100

        loss_pct = (max_loss / balance) * 100

        if loss_pct <= 2:
            return 10
        elif loss_pct <= 5:
            return 30
        elif loss_pct <= 10:
            return 50
        elif loss_pct <= 20:
            return 70
        else:
            return 90


class OptionsOrderService:
    """Service for managing options orders."""

    def __init__(self, session: AsyncSession):
        """Initialize options order service."""
        self.session = session
        self.strategy_recognizer = StrategyRecognizer()
        self.greeks_calculator = GreeksCalculator()
        self.risk_analyzer = OptionRiskAnalyzer()

    async def validate_approval_level(
        self,
        user: User,
        strategy: OptionStrategy,
        legs: List[Dict]
    ) -> Tuple[bool, OptionApprovalLevel, str]:
        """
        Validate user has appropriate options approval level.

        Args:
            user: User placing the order
            strategy: Identified strategy type
            legs: Option legs

        Returns:
            Tuple of (is_approved, required_level, message)
        """
        # Get user's approval level from broker link or account
        # This would connect to TastyTrade API to check actual approval
        user_level = OptionApprovalLevel.LEVEL_2  # Placeholder

        required_level = self._get_required_approval(strategy, legs)

        # Compare levels
        level_values = {
            OptionApprovalLevel.LEVEL_0: 0,
            OptionApprovalLevel.LEVEL_1: 1,
            OptionApprovalLevel.LEVEL_2: 2,
            OptionApprovalLevel.LEVEL_3: 3
        }

        is_approved = level_values[user_level] >= level_values[required_level]

        message = "Approved" if is_approved else f"Requires {required_level.value}"

        return is_approved, required_level, message

    def _get_required_approval(self, strategy: OptionStrategy, legs: List[Dict]) -> OptionApprovalLevel:
        """Determine required approval level for strategy."""
        # Check for naked options (Level 3)
        has_naked = any(
            'sell' in leg.get('action', leg.get('side', '')).lower() and
            strategy not in [OptionStrategy.COVERED_CALL, OptionStrategy.CASH_SECURED_PUT]
            for leg in legs
        )

        if has_naked:
            return OptionApprovalLevel.LEVEL_3

        # Check for spreads (Level 2)
        if len(legs) >= 2:
            return OptionApprovalLevel.LEVEL_2

        # Check for covered strategies (Level 1)
        if strategy in [OptionStrategy.COVERED_CALL, OptionStrategy.CASH_SECURED_PUT]:
            return OptionApprovalLevel.LEVEL_1

        # Long single options (Level 2)
        if len(legs) == 1 and 'buy' in legs[0]['action'].lower():
            return OptionApprovalLevel.LEVEL_2

        return OptionApprovalLevel.LEVEL_3

    async def create_options_preview(
        self,
        user: User,
        account_id: str,
        legs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create preview for options order.

        Args:
            user: User creating the order
            account_id: Account ID
            legs: List of option legs

        Returns:
            Preview with strategy analysis and risk assessment
        """
        # Identify strategy
        strategy, strategy_name = self.strategy_recognizer.identify_strategy(legs)

        # Validate approval level
        is_approved, required_level, approval_msg = await self.validate_approval_level(
            user, strategy, legs
        )

        if not is_approved:
            return {
                "error": "Insufficient options approval level",
                "required_level": required_level.value,
                "message": approval_msg
            }

        # Get current market data (would fetch from TastyTrade)
        underlying_price = 150.00  # Placeholder
        risk_free_rate = 0.05

        # Calculate Greeks for each leg
        for leg in legs:
            # Calculate time to expiry
            expiry = leg['expiration_date']
            days_to_expiry = (expiry - datetime.now()).days
            time_to_expiry = days_to_expiry / 365

            # Calculate Greeks
            greeks = self.greeks_calculator.calculate_greeks(
                spot_price=underlying_price,
                strike_price=leg['strike_price'],
                time_to_expiry=time_to_expiry,
                risk_free_rate=risk_free_rate,
                implied_volatility=leg.get('implied_volatility', 0.25),
                option_type=leg['option_type']
            )
            leg['greeks'] = greeks

        # Assess risk
        # Get account balance (would fetch from TastyTrade)
        account_balance = 100000.00  # Placeholder

        risk_assessment = self.risk_analyzer.assess_strategy_risk(
            legs, underlying_price, account_balance
        )

        # Create preview
        preview = {
            "strategy": strategy.value,
            "strategy_name": strategy_name,
            "legs": legs,
            "risk_assessment": risk_assessment,
            "approval": {
                "approved": is_approved,
                "required_level": required_level.value,
                "user_level": OptionApprovalLevel.LEVEL_2.value  # Placeholder
            },
            "underlying_price": underlying_price,
            "expires_at": datetime.utcnow() + timedelta(minutes=2)
        }

        logger.info(f"Created options preview for {strategy_name}")

        return preview