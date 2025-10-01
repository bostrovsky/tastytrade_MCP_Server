"""Position analytics and correlation analysis."""
import math
from decimal import Decimal
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta

from .models import CorrelationAnalysis, PositionAnalytics


class PositionAnalyticsService:
    """Provides position analytics and correlation analysis."""

    def __init__(self):
        """Initialize analytics service."""
        pass

    async def analyze_correlation(
        self,
        positions: List[Dict[str, Any]],
        lookback_days: int = 30,
        correlation_threshold: float = 0.7
    ) -> CorrelationAnalysis:
        """Analyze correlation between positions."""
        if len(positions) < 2:
            return CorrelationAnalysis(
                high_correlations=[],
                concentration_risks=[],
                diversification_score=10.0,
                recommendations=["Add more positions for diversification"]
            )

        # Get symbols from positions
        symbols = [pos.get("symbol", "") for pos in positions if pos.get("symbol")]

        # Calculate correlation matrix (simplified simulation)
        correlations = await self._calculate_correlation_matrix(symbols, lookback_days)

        # Find high correlations
        high_correlations = []
        for (symbol1, symbol2), correlation in correlations.items():
            if abs(correlation) >= correlation_threshold:
                risk_level = "high" if abs(correlation) >= 0.8 else "medium"
                high_correlations.append({
                    "symbol1": symbol1,
                    "symbol2": symbol2,
                    "correlation": correlation,
                    "risk_level": risk_level
                })

        # Check concentration risks
        concentration_risks = self._check_concentration_risks(positions)

        # Calculate diversification score
        diversification_score = self._calculate_diversification_score(positions, correlations)

        # Generate recommendations
        recommendations = self._generate_diversification_recommendations(
            high_correlations, concentration_risks, len(positions)
        )

        return CorrelationAnalysis(
            high_correlations=high_correlations,
            concentration_risks=concentration_risks,
            diversification_score=diversification_score,
            recommendations=recommendations
        )

    async def generate_position_analytics(
        self,
        positions: List[Dict[str, Any]]
    ) -> PositionAnalytics:
        """Generate comprehensive position analytics."""
        if not positions:
            return PositionAnalytics(
                total_positions=0,
                total_market_value=Decimal("0"),
                total_unrealized_pnl=Decimal("0"),
                total_realized_pnl=Decimal("0"),
                win_rate=0.0,
                largest_winner=Decimal("0"),
                largest_loser=Decimal("0")
            )

        # Calculate basic metrics
        total_positions = len(positions)
        total_market_value = sum(Decimal(str(pos.get("market_value", 0))) for pos in positions)
        total_unrealized_pnl = sum(Decimal(str(pos.get("unrealized_pnl", 0))) for pos in positions)
        total_realized_pnl = sum(Decimal(str(pos.get("realized_pnl", 0))) for pos in positions)

        # Calculate win/loss statistics
        winners = [pos for pos in positions if pos.get("unrealized_pnl", 0) > 0]
        losers = [pos for pos in positions if pos.get("unrealized_pnl", 0) < 0]

        win_rate = (len(winners) / total_positions * 100) if total_positions > 0 else 0.0

        # Find largest winner/loser
        largest_winner = max((Decimal(str(pos.get("unrealized_pnl", 0))) for pos in winners), default=Decimal("0"))
        largest_loser = min((Decimal(str(pos.get("unrealized_pnl", 0))) for pos in losers), default=Decimal("0"))

        # Calculate advanced metrics (simplified)
        portfolio_beta = await self._calculate_portfolio_beta(positions)
        sharpe_ratio = await self._calculate_sharpe_ratio(positions)
        max_drawdown = await self._calculate_max_drawdown(positions)

        return PositionAnalytics(
            total_positions=total_positions,
            total_market_value=total_market_value,
            total_unrealized_pnl=total_unrealized_pnl,
            total_realized_pnl=total_realized_pnl,
            win_rate=win_rate,
            largest_winner=largest_winner,
            largest_loser=largest_loser,
            portfolio_beta=portfolio_beta,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown
        )

    async def _calculate_correlation_matrix(
        self,
        symbols: List[str],
        lookback_days: int
    ) -> Dict[Tuple[str, str], float]:
        """Calculate correlation matrix between symbols."""
        correlations = {}

        # Simplified correlation calculation (in real implementation, fetch historical data)
        for i, symbol1 in enumerate(symbols):
            for j, symbol2 in enumerate(symbols[i + 1:], i + 1):
                # Simulate correlation based on sector/industry similarity
                correlation = self._simulate_correlation(symbol1, symbol2)
                correlations[(symbol1, symbol2)] = correlation

        return correlations

    def _simulate_correlation(self, symbol1: str, symbol2: str) -> float:
        """Simulate correlation between two symbols."""
        # Simple simulation based on symbol similarity
        # In real implementation, use historical price data

        # Tech stocks tend to be correlated
        tech_symbols = {"AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"}
        if symbol1 in tech_symbols and symbol2 in tech_symbols:
            return 0.75  # High correlation for tech stocks

        # Financial stocks correlation
        finance_symbols = {"JPM", "BAC", "WFC", "GS", "C"}
        if symbol1 in finance_symbols and symbol2 in finance_symbols:
            return 0.68

        # Different sectors - lower correlation
        return 0.35

    def _check_concentration_risks(self, positions: List[Dict[str, Any]]) -> List[str]:
        """Check for position concentration risks."""
        risks = []

        if not positions:
            return risks

        total_value = sum(abs(pos.get("market_value", 0)) for pos in positions)
        if total_value == 0:
            return risks

        # Check individual position concentration
        for position in positions:
            symbol = position.get("symbol", "")
            market_value = abs(position.get("market_value", 0))
            concentration = market_value / total_value

            if concentration > 0.25:  # 25% threshold
                risks.append(f"High concentration in {symbol}: {concentration:.1%} of portfolio")

        # Check sector concentration
        sector_exposure = self._calculate_sector_exposure(positions)
        for sector, exposure in sector_exposure.items():
            if exposure > 0.4:  # 40% threshold
                risks.append(f"High sector concentration in {sector}: {exposure:.1%}")

        return risks

    def _calculate_sector_exposure(self, positions: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate exposure by sector."""
        # Simplified sector mapping
        sector_map = {
            "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
            "AMZN": "Consumer Discretionary", "TSLA": "Consumer Discretionary",
            "JPM": "Financials", "BAC": "Financials", "WFC": "Financials",
            "XOM": "Energy", "CVX": "Energy",
            "JNJ": "Healthcare", "PFE": "Healthcare"
        }

        total_value = sum(abs(pos.get("market_value", 0)) for pos in positions)
        if total_value == 0:
            return {}

        sector_values = {}
        for position in positions:
            symbol = position.get("symbol", "")
            sector = sector_map.get(symbol, "Other")
            market_value = abs(position.get("market_value", 0))

            if sector not in sector_values:
                sector_values[sector] = 0
            sector_values[sector] += market_value

        # Convert to percentages
        return {sector: value / total_value for sector, value in sector_values.items()}

    def _calculate_diversification_score(
        self,
        positions: List[Dict[str, Any]],
        correlations: Dict[Tuple[str, str], float]
    ) -> float:
        """Calculate portfolio diversification score (0-10 scale)."""
        if len(positions) < 2:
            return 5.0

        # Base score from number of positions
        position_score = min(len(positions) / 10, 1.0) * 4  # Max 4 points for positions

        # Correlation penalty
        avg_correlation = sum(abs(corr) for corr in correlations.values()) / len(correlations) if correlations else 0
        correlation_score = (1 - avg_correlation) * 4  # Max 4 points for low correlation

        # Concentration penalty
        concentration_risks = self._check_concentration_risks(positions)
        concentration_score = max(0, 2 - len(concentration_risks) * 0.5)  # Max 2 points

        return min(position_score + correlation_score + concentration_score, 10.0)

    def _generate_diversification_recommendations(
        self,
        high_correlations: List[Dict[str, Any]],
        concentration_risks: List[str],
        num_positions: int
    ) -> List[str]:
        """Generate diversification recommendations."""
        recommendations = []

        if num_positions < 5:
            recommendations.append("Consider adding more positions to improve diversification")

        if high_correlations:
            recommendations.append("Reduce exposure to highly correlated positions")

        if concentration_risks:
            recommendations.append("Reduce concentration in overweight positions")

        if not recommendations:
            recommendations.append("Portfolio shows good diversification characteristics")

        return recommendations

    async def _calculate_portfolio_beta(self, positions: List[Dict[str, Any]]) -> float:
        """Calculate portfolio beta (simplified)."""
        # Simplified beta calculation
        # In real implementation, use market data and regression
        return 1.0

    async def _calculate_sharpe_ratio(self, positions: List[Dict[str, Any]]) -> float:
        """Calculate Sharpe ratio (simplified)."""
        # Simplified Sharpe ratio calculation
        # In real implementation, use return and volatility data
        return 0.8

    async def _calculate_max_drawdown(self, positions: List[Dict[str, Any]]) -> float:
        """Calculate maximum drawdown (simplified)."""
        # Simplified max drawdown calculation
        # In real implementation, use historical portfolio values
        return -0.15  # -15% max drawdown