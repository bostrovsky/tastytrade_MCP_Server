"""Strategy framework for backtesting."""
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any

import pandas as pd
import numpy as np

from tastytrade_mcp.models.backtesting import (
    TradingSignal, BacktestConfig, PortfolioSnapshot, PositionSizeMethod
)
from tastytrade_mcp.models.trading import OrderSide, OrderType
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class TradingStrategy(ABC):
    """Abstract base class for trading strategies."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.parameters: Dict[str, Any] = {}

    @abstractmethod
    async def generate_signals(self, timestamp: datetime,
                             market_data: Dict[str, Dict[str, float]],
                             portfolio: PortfolioSnapshot,
                             config: BacktestConfig) -> List[TradingSignal]:
        """Generate trading signals based on market data and portfolio state."""
        pass

    def set_parameters(self, **kwargs):
        """Set strategy parameters."""
        self.parameters.update(kwargs)

    def get_parameter(self, name: str, default: Any = None) -> Any:
        """Get strategy parameter value."""
        return self.parameters.get(name, default)


class MovingAverageCrossover(TradingStrategy):
    """Simple moving average crossover strategy."""

    def __init__(self, short_window: int = 20, long_window: int = 50):
        super().__init__(
            name="Moving Average Crossover",
            description=f"Buy when {short_window}-day MA crosses above {long_window}-day MA"
        )
        self.short_window = short_window
        self.long_window = long_window
        self.price_history: Dict[str, List[float]] = {}

    async def generate_signals(self, timestamp: datetime,
                             market_data: Dict[str, Dict[str, float]],
                             portfolio: PortfolioSnapshot,
                             config: BacktestConfig) -> List[TradingSignal]:
        """Generate signals based on moving average crossover."""
        signals = []

        for symbol, data in market_data.items():
            # Update price history
            if symbol not in self.price_history:
                self.price_history[symbol] = []

            self.price_history[symbol].append(data['close'])

            # Keep only necessary history
            max_window = max(self.short_window, self.long_window)
            if len(self.price_history[symbol]) > max_window + 10:
                self.price_history[symbol] = self.price_history[symbol][-max_window:]

            # Check if we have enough data
            if len(self.price_history[symbol]) < self.long_window:
                continue

            # Calculate moving averages
            prices = np.array(self.price_history[symbol])
            short_ma = np.mean(prices[-self.short_window:])
            long_ma = np.mean(prices[-self.long_window:])

            # Previous moving averages for crossover detection
            if len(prices) > self.long_window:
                prev_short_ma = np.mean(prices[-(self.short_window + 1):-1])
                prev_long_ma = np.mean(prices[-(self.long_window + 1):-1])

                current_position = portfolio.positions.get(symbol, 0)

                # Buy signal: short MA crosses above long MA
                if (prev_short_ma <= prev_long_ma and short_ma > long_ma and
                    current_position <= 0):

                    quantity = self._calculate_position_size(
                        symbol, data['close'], portfolio, config
                    )

                    if quantity > 0:
                        signals.append(TradingSignal(
                            timestamp=timestamp,
                            symbol=symbol,
                            side=OrderSide.BUY,
                            quantity=quantity,
                            order_type=OrderType.MARKET,
                            confidence=0.8,
                            reason=f"MA crossover: {short_ma:.2f} > {long_ma:.2f}"
                        ))

                # Sell signal: short MA crosses below long MA
                elif (prev_short_ma >= prev_long_ma and short_ma < long_ma and
                      current_position > 0):

                    signals.append(TradingSignal(
                        timestamp=timestamp,
                        symbol=symbol,
                        side=OrderSide.SELL,
                        quantity=current_position,
                        order_type=OrderType.MARKET,
                        confidence=0.8,
                        reason=f"MA crossover: {short_ma:.2f} < {long_ma:.2f}"
                    ))

        return signals

    def _calculate_position_size(self, symbol: str, price: float,
                               portfolio: PortfolioSnapshot,
                               config: BacktestConfig) -> int:
        """Calculate position size based on configuration."""
        if config.position_size_method == PositionSizeMethod.FIXED_SHARES:
            return int(config.position_size_value)

        elif config.position_size_method == PositionSizeMethod.FIXED_DOLLARS:
            return int(config.position_size_value / price)

        elif config.position_size_method == PositionSizeMethod.PERCENT_PORTFOLIO:
            allocation = float(portfolio.total_value) * float(config.position_size_value) / 100
            return int(allocation / price)

        else:
            # Default to fixed dollar amount
            return int(1000 / price)


class MeanReversion(TradingStrategy):
    """Mean reversion strategy using Z-score."""

    def __init__(self, lookback_window: int = 20, z_threshold: float = 2.0):
        super().__init__(
            name="Mean Reversion",
            description=f"Trade when price deviates {z_threshold} standard deviations from {lookback_window}-day mean"
        )
        self.lookback_window = lookback_window
        self.z_threshold = z_threshold
        self.price_history: Dict[str, List[float]] = {}

    async def generate_signals(self, timestamp: datetime,
                             market_data: Dict[str, Dict[str, float]],
                             portfolio: PortfolioSnapshot,
                             config: BacktestConfig) -> List[TradingSignal]:
        """Generate signals based on mean reversion."""
        signals = []

        for symbol, data in market_data.items():
            # Update price history
            if symbol not in self.price_history:
                self.price_history[symbol] = []

            self.price_history[symbol].append(data['close'])

            # Keep only necessary history
            if len(self.price_history[symbol]) > self.lookback_window + 10:
                self.price_history[symbol] = self.price_history[symbol][-self.lookback_window:]

            # Check if we have enough data
            if len(self.price_history[symbol]) < self.lookback_window:
                continue

            # Calculate Z-score
            prices = np.array(self.price_history[symbol])
            mean_price = np.mean(prices[:-1])  # Exclude current price
            std_price = np.std(prices[:-1])

            if std_price == 0:
                continue

            current_price = prices[-1]
            z_score = (current_price - mean_price) / std_price

            current_position = portfolio.positions.get(symbol, 0)

            # Buy signal: price is oversold (low Z-score)
            if z_score < -self.z_threshold and current_position <= 0:
                quantity = self._calculate_position_size(
                    symbol, data['close'], portfolio, config
                )

                if quantity > 0:
                    signals.append(TradingSignal(
                        timestamp=timestamp,
                        symbol=symbol,
                        side=OrderSide.BUY,
                        quantity=quantity,
                        order_type=OrderType.MARKET,
                        confidence=min(0.9, abs(z_score) / 5),  # Higher confidence for larger deviations
                        reason=f"Mean reversion buy: Z-score = {z_score:.2f}"
                    ))

            # Sell signal: price is overbought (high Z-score) or mean reversion
            elif (z_score > self.z_threshold or abs(z_score) < 0.5) and current_position > 0:
                signals.append(TradingSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    side=OrderSide.SELL,
                    quantity=current_position,
                    order_type=OrderType.MARKET,
                    confidence=0.8,
                    reason=f"Mean reversion sell: Z-score = {z_score:.2f}"
                ))

        return signals

    def _calculate_position_size(self, symbol: str, price: float,
                               portfolio: PortfolioSnapshot,
                               config: BacktestConfig) -> int:
        """Calculate position size based on configuration."""
        if config.position_size_method == PositionSizeMethod.FIXED_SHARES:
            return int(config.position_size_value)

        elif config.position_size_method == PositionSizeMethod.FIXED_DOLLARS:
            return int(config.position_size_value / price)

        elif config.position_size_method == PositionSizeMethod.PERCENT_PORTFOLIO:
            allocation = float(portfolio.total_value) * float(config.position_size_value) / 100
            return int(allocation / price)

        else:
            return int(1000 / price)


class MomentumStrategy(TradingStrategy):
    """Momentum strategy based on price momentum."""

    def __init__(self, lookback_window: int = 10, momentum_threshold: float = 0.02):
        super().__init__(
            name="Momentum Strategy",
            description=f"Trade based on {lookback_window}-day momentum above {momentum_threshold*100}%"
        )
        self.lookback_window = lookback_window
        self.momentum_threshold = momentum_threshold
        self.price_history: Dict[str, List[float]] = {}

    async def generate_signals(self, timestamp: datetime,
                             market_data: Dict[str, Dict[str, float]],
                             portfolio: PortfolioSnapshot,
                             config: BacktestConfig) -> List[TradingSignal]:
        """Generate signals based on momentum."""
        signals = []

        for symbol, data in market_data.items():
            # Update price history
            if symbol not in self.price_history:
                self.price_history[symbol] = []

            self.price_history[symbol].append(data['close'])

            # Keep only necessary history
            if len(self.price_history[symbol]) > self.lookback_window + 10:
                self.price_history[symbol] = self.price_history[symbol][-self.lookback_window:]

            # Check if we have enough data
            if len(self.price_history[symbol]) < self.lookback_window:
                continue

            # Calculate momentum
            prices = np.array(self.price_history[symbol])
            momentum = (prices[-1] - prices[-self.lookback_window]) / prices[-self.lookback_window]

            current_position = portfolio.positions.get(symbol, 0)

            # Buy signal: positive momentum
            if momentum > self.momentum_threshold and current_position <= 0:
                quantity = self._calculate_position_size(
                    symbol, data['close'], portfolio, config
                )

                if quantity > 0:
                    signals.append(TradingSignal(
                        timestamp=timestamp,
                        symbol=symbol,
                        side=OrderSide.BUY,
                        quantity=quantity,
                        order_type=OrderType.MARKET,
                        confidence=min(0.9, momentum * 5),  # Scale confidence with momentum
                        reason=f"Positive momentum: {momentum:.2%}"
                    ))

            # Sell signal: negative momentum
            elif momentum < -self.momentum_threshold and current_position > 0:
                signals.append(TradingSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    side=OrderSide.SELL,
                    quantity=current_position,
                    order_type=OrderType.MARKET,
                    confidence=0.8,
                    reason=f"Negative momentum: {momentum:.2%}"
                ))

        return signals

    def _calculate_position_size(self, symbol: str, price: float,
                               portfolio: PortfolioSnapshot,
                               config: BacktestConfig) -> int:
        """Calculate position size based on configuration."""
        if config.position_size_method == PositionSizeMethod.FIXED_SHARES:
            return int(config.position_size_value)

        elif config.position_size_method == PositionSizeMethod.FIXED_DOLLARS:
            return int(config.position_size_value / price)

        elif config.position_size_method == PositionSizeMethod.PERCENT_PORTFOLIO:
            allocation = float(portfolio.total_value) * float(config.position_size_value) / 100
            return int(allocation / price)

        else:
            return int(1000 / price)


class BuyAndHold(TradingStrategy):
    """Simple buy and hold strategy."""

    def __init__(self):
        super().__init__(
            name="Buy and Hold",
            description="Buy once at the beginning and hold until the end"
        )
        self.initial_purchase_made = False

    async def generate_signals(self, timestamp: datetime,
                             market_data: Dict[str, Dict[str, float]],
                             portfolio: PortfolioSnapshot,
                             config: BacktestConfig) -> List[TradingSignal]:
        """Generate buy signal only once at the beginning."""
        if self.initial_purchase_made:
            return []

        signals = []

        # Buy each symbol once
        for symbol, data in market_data.items():
            current_position = portfolio.positions.get(symbol, 0)

            if current_position == 0:
                quantity = self._calculate_position_size(
                    symbol, data['close'], portfolio, config
                )

                if quantity > 0:
                    signals.append(TradingSignal(
                        timestamp=timestamp,
                        symbol=symbol,
                        side=OrderSide.BUY,
                        quantity=quantity,
                        order_type=OrderType.MARKET,
                        confidence=1.0,
                        reason="Initial buy and hold purchase"
                    ))

        if signals:
            self.initial_purchase_made = True

        return signals

    def _calculate_position_size(self, symbol: str, price: float,
                               portfolio: PortfolioSnapshot,
                               config: BacktestConfig) -> int:
        """Calculate equal-weight position size."""
        # For buy-and-hold, divide portfolio equally among all symbols
        num_symbols = 5  # Default assumption
        allocation = float(portfolio.total_value) / num_symbols
        return int(allocation / price)


# Strategy Registry
STRATEGY_REGISTRY = {
    "moving_average_crossover": MovingAverageCrossover,
    "mean_reversion": MeanReversion,
    "momentum": MomentumStrategy,
    "buy_and_hold": BuyAndHold,
}


def get_strategy(strategy_name: str, **kwargs) -> TradingStrategy:
    """Get strategy instance by name."""
    if strategy_name not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy: {strategy_name}. Available: {list(STRATEGY_REGISTRY.keys())}")

    strategy_class = STRATEGY_REGISTRY[strategy_name]
    return strategy_class(**kwargs)


def list_strategies() -> List[Dict[str, str]]:
    """List all available strategies."""
    strategies = []
    for name, strategy_class in STRATEGY_REGISTRY.items():
        # Create temporary instance to get description
        temp_instance = strategy_class()
        strategies.append({
            "name": name,
            "display_name": temp_instance.name,
            "description": temp_instance.description
        })
    return strategies