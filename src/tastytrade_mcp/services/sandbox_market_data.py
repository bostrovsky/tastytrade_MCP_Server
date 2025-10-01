"""Sandbox market data feed simulation service."""
import asyncio
import random
import math
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, AsyncGenerator
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
import numpy as np

from tastytrade_mcp.models.sandbox import SandboxMarketData, SandboxConfiguration
from tastytrade_mcp.db.session import get_async_session

logger = logging.getLogger(__name__)


class SandboxMarketDataService:
    """Realistic market data simulation service."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._active_feeds: Dict[str, bool] = {}
        self._price_history: Dict[str, List[Decimal]] = {}

    async def get_real_time_quote(self, symbol: str) -> Dict[str, Any]:
        """Get simulated real-time quote for a symbol."""
        market_data = await self._get_or_update_market_data(symbol)

        return {
            "symbol": symbol,
            "bid": float(market_data.bid),
            "ask": float(market_data.ask),
            "last": float(market_data.last),
            "bid_size": market_data.bid_size,
            "ask_size": market_data.ask_size,
            "volume": market_data.volume,
            "open": float(market_data.open_price),
            "high": float(market_data.high),
            "low": float(market_data.low),
            "close": float(market_data.close),
            "change": float(market_data.last - market_data.close),
            "change_percent": float(((market_data.last - market_data.close) / market_data.close) * 100),
            "quote_time": market_data.updated_at.isoformat(),
            "market_status": self._get_market_status(),
            "is_simulated": True,
            "sandbox_info": {
                "volatility": float(market_data.volatility),
                "data_quality": "excellent",
                "last_update": market_data.updated_at.isoformat()
            }
        }

    async def get_multiple_quotes(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get quotes for multiple symbols efficiently."""
        quotes = {}
        for symbol in symbols:
            try:
                quotes[symbol] = await self.get_real_time_quote(symbol)
            except Exception as e:
                logger.error(f"Error getting quote for {symbol}: {e}")
                quotes[symbol] = {"error": str(e), "symbol": symbol}

        return quotes

    async def get_historical_data(
        self,
        symbol: str,
        period: str = "1D",
        interval: str = "1m",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Generate simulated historical data."""
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=30)
        if not end_date:
            end_date = datetime.utcnow()

        # Get current market data for reference
        current_data = await self._get_or_update_market_data(symbol)
        base_price = current_data.last
        volatility = current_data.volatility

        # Generate historical price series
        data_points = self._generate_historical_series(
            base_price, volatility, start_date, end_date, interval
        )

        return {
            "symbol": symbol,
            "period": period,
            "interval": interval,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "data_points": len(data_points),
            "candles": data_points,
            "is_simulated": True,
            "generated_at": datetime.utcnow().isoformat()
        }

    def _generate_historical_series(
        self,
        base_price: Decimal,
        volatility: Decimal,
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> List[Dict[str, Any]]:
        """Generate realistic OHLCV data using geometric Brownian motion."""
        # Determine time delta based on interval
        interval_minutes = self._parse_interval(interval)
        total_minutes = int((end_date - start_date).total_seconds() / 60)
        num_points = min(total_minutes // interval_minutes, 10000)  # Limit to reasonable size

        if num_points <= 0:
            return []

        # Set random seed for consistency
        np.random.seed(hash(f"{base_price}{start_date}") % 2**32)

        # Generate price series using geometric Brownian motion
        dt = interval_minutes / (252 * 24 * 60)  # Convert to years
        drift = 0.05  # 5% annual drift
        vol = float(volatility)

        prices = [float(base_price)]
        for _ in range(num_points - 1):
            random_shock = np.random.normal(0, 1)
            price_change = prices[-1] * (drift * dt + vol * math.sqrt(dt) * random_shock)
            new_price = max(prices[-1] + price_change, 0.01)  # Prevent negative prices
            prices.append(new_price)

        # Convert to OHLCV candles
        candles = []
        current_time = start_date

        for i, price in enumerate(prices):
            # Generate realistic OHLC from price
            open_price = prices[i-1] if i > 0 else price
            close_price = price

            # Add some intrabar volatility
            intrabar_vol = vol * 0.3  # Reduced volatility within bar
            high_multiplier = 1 + abs(np.random.normal(0, intrabar_vol * 0.5))
            low_multiplier = 1 - abs(np.random.normal(0, intrabar_vol * 0.5))

            high = max(open_price, close_price) * high_multiplier
            low = min(open_price, close_price) * low_multiplier

            # Ensure OHLC logic is valid
            high = max(high, open_price, close_price)
            low = min(low, open_price, close_price)

            # Generate volume (correlated with price movement)
            price_change_pct = abs((close_price - open_price) / open_price) if open_price > 0 else 0
            base_volume = random.randint(50000, 500000)
            volume_multiplier = 1 + (price_change_pct * 2)  # Higher volume on larger moves
            volume = int(base_volume * volume_multiplier)

            candles.append({
                "timestamp": current_time.isoformat(),
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close_price, 2),
                "volume": volume,
                "vwap": round((high + low + close_price) / 3, 2)
            })

            current_time += timedelta(minutes=interval_minutes)

        return candles

    def _parse_interval(self, interval: str) -> int:
        """Parse interval string to minutes."""
        interval = interval.lower()
        if interval.endswith('m'):
            return int(interval[:-1])
        elif interval.endswith('h'):
            return int(interval[:-1]) * 60
        elif interval.endswith('d'):
            return int(interval[:-1]) * 24 * 60
        else:
            return 1  # Default to 1 minute

    async def start_streaming_feed(self, symbols: List[str]) -> AsyncGenerator[Dict[str, Any], None]:
        """Start streaming market data feed for symbols."""
        logger.info(f"Starting sandbox streaming feed for {len(symbols)} symbols")

        # Mark feeds as active
        for symbol in symbols:
            self._active_feeds[symbol] = True

        try:
            while any(self._active_feeds.get(symbol, False) for symbol in symbols):
                # Generate updates for all symbols
                updates = {}
                for symbol in symbols:
                    if self._active_feeds.get(symbol, False):
                        try:
                            # Update market data with realistic price movement
                            await self._update_real_time_price(symbol)
                            quote = await self.get_real_time_quote(symbol)
                            updates[symbol] = quote
                        except Exception as e:
                            logger.error(f"Error updating {symbol}: {e}")

                if updates:
                    yield {
                        "type": "quote_update",
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": updates
                    }

                # Stream at ~10Hz for realistic feel
                await asyncio.sleep(0.1)

        finally:
            # Clean up
            for symbol in symbols:
                self._active_feeds[symbol] = False

    async def stop_streaming_feed(self, symbols: List[str]):
        """Stop streaming feed for symbols."""
        for symbol in symbols:
            self._active_feeds[symbol] = False
        logger.info(f"Stopped sandbox streaming feed for {symbols}")

    async def _update_real_time_price(self, symbol: str):
        """Update market data with realistic price movements."""
        market_data = await self._get_or_update_market_data(symbol)

        # Apply geometric Brownian motion for realistic price movement
        dt = 1.0 / (252 * 24 * 60 * 60 * 10)  # ~0.1 second intervals
        drift = 0.05  # 5% annual drift
        vol = float(market_data.volatility)

        # Generate price change
        random_shock = random.gauss(0, 1)
        price_change_pct = drift * dt + vol * math.sqrt(dt) * random_shock

        # Update last price
        new_last = market_data.last * Decimal(str(1 + price_change_pct))
        new_last = new_last.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # Update bid/ask with spread
        spread_pct = random.uniform(0.0005, 0.002)  # 0.05% to 0.2% spread
        spread = new_last * Decimal(str(spread_pct))

        new_bid = new_last - spread / 2
        new_ask = new_last + spread / 2

        # Update high/low for the day
        new_high = max(market_data.high, new_last)
        new_low = min(market_data.low, new_last)

        # Update volume (add random volume)
        volume_increment = random.randint(100, 10000)

        # Apply updates
        await self.session.execute(
            update(SandboxMarketData)
            .where(SandboxMarketData.symbol == symbol)
            .values(
                bid=new_bid,
                ask=new_ask,
                last=new_last,
                high=new_high,
                low=new_low,
                volume=SandboxMarketData.volume + volume_increment,
                updated_at=datetime.utcnow()
            )
        )
        await self.session.commit()

    async def _get_or_update_market_data(self, symbol: str) -> SandboxMarketData:
        """Get existing market data or create/update it."""
        query = select(SandboxMarketData).where(SandboxMarketData.symbol == symbol)
        result = await self.session.execute(query)
        market_data = result.scalar_one_or_none()

        if not market_data:
            # Create new market data
            market_data = await self._create_initial_market_data(symbol)
        else:
            # Check if data is stale (older than 1 minute)
            if datetime.utcnow() - market_data.updated_at > timedelta(minutes=1):
                # Update with small price movement
                await self._update_real_time_price(symbol)
                await self.session.refresh(market_data)

        return market_data

    async def _create_initial_market_data(self, symbol: str) -> SandboxMarketData:
        """Create initial market data for a new symbol."""
        # Generate realistic initial prices based on symbol characteristics
        base_price = self._generate_initial_price(symbol)
        volatility = Decimal(str(random.uniform(0.15, 0.45)))  # 15-45% annualized volatility

        # Create realistic spread
        spread_pct = random.uniform(0.001, 0.003)  # 0.1% to 0.3%
        spread = base_price * Decimal(str(spread_pct))

        # Generate daily range
        daily_range = base_price * volatility / Decimal('16')  # Approximate daily range
        open_price = base_price * Decimal(str(random.uniform(0.995, 1.005)))
        high = base_price + daily_range * Decimal(str(random.uniform(0.5, 1.0)))
        low = base_price - daily_range * Decimal(str(random.uniform(0.5, 1.0)))
        close = base_price * Decimal(str(random.uniform(0.998, 1.002)))

        market_data = SandboxMarketData(
            symbol=symbol,
            bid=base_price - spread / 2,
            ask=base_price + spread / 2,
            last=base_price,
            open_price=open_price,
            high=high,
            low=low,
            close=close,
            volume=random.randint(100000, 5000000),
            bid_size=random.randint(100, 1000) * 100,
            ask_size=random.randint(100, 1000) * 100,
            volatility=volatility
        )

        self.session.add(market_data)
        await self.session.commit()
        await self.session.refresh(market_data)

        logger.info(f"Created initial market data for {symbol} at ${base_price}")
        return market_data

    def _generate_initial_price(self, symbol: str) -> Decimal:
        """Generate realistic initial price based on symbol characteristics."""
        # Use symbol hash for consistent pricing
        symbol_hash = hash(symbol) % 10000

        if symbol.startswith('SPY'):
            return Decimal(str(400 + (symbol_hash % 100)))
        elif symbol.startswith('QQQ'):
            return Decimal(str(350 + (symbol_hash % 80)))
        elif symbol.startswith('AAPL'):
            return Decimal(str(150 + (symbol_hash % 50)))
        elif symbol.startswith('TSLA'):
            return Decimal(str(200 + (symbol_hash % 300)))
        elif symbol.startswith('MSFT'):
            return Decimal(str(300 + (symbol_hash % 100)))
        elif len(symbol) <= 4:  # Likely a stock
            return Decimal(str(50 + (symbol_hash % 450)))
        else:  # Options or other instruments
            return Decimal(str(10 + (symbol_hash % 90)))

    def _get_market_status(self) -> str:
        """Get current market status based on time."""
        now = datetime.utcnow()
        # Convert to ET (approximate - doesn't handle DST perfectly)
        et_time = now - timedelta(hours=5)
        hour = et_time.hour
        minute = et_time.minute
        weekday = et_time.weekday()

        # Weekend
        if weekday >= 5:
            return "closed"

        # Regular trading hours: 9:30 AM - 4:00 PM ET
        if (hour == 9 and minute >= 30) or (10 <= hour < 16):
            return "open"
        elif hour == 16 and minute == 0:
            return "closing"
        elif 4 <= hour < 9:
            return "pre_market"
        elif hour >= 16:
            return "after_hours"
        else:
            return "closed"

    async def get_options_chain(self, underlying_symbol: str, expiration_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Generate simulated options chain data."""
        # Get underlying price
        underlying_data = await self._get_or_update_market_data(underlying_symbol)
        underlying_price = underlying_data.last

        # Generate expiration dates if not provided
        if not expiration_date:
            # Generate next few monthly expirations
            expirations = self._generate_option_expirations()
        else:
            expirations = [expiration_date]

        chain_data = {
            "underlying_symbol": underlying_symbol,
            "underlying_price": float(underlying_price),
            "expirations": []
        }

        for exp_date in expirations[:6]:  # Limit to 6 expirations
            strikes = self._generate_option_strikes(underlying_price)
            calls = []
            puts = []

            for strike in strikes:
                # Generate realistic option prices using Black-Scholes approximation
                call_price, put_price = self._calculate_option_prices(
                    underlying_price, strike, exp_date, underlying_data.volatility
                )

                calls.append({
                    "strike": float(strike),
                    "bid": float(call_price * Decimal('0.98')),
                    "ask": float(call_price * Decimal('1.02')),
                    "last": float(call_price),
                    "volume": random.randint(0, 1000),
                    "open_interest": random.randint(0, 5000),
                    "implied_volatility": float(underlying_data.volatility) + random.uniform(-0.05, 0.05),
                    "delta": self._calculate_delta(underlying_price, strike, exp_date, "call"),
                    "gamma": self._calculate_gamma(underlying_price, strike, exp_date),
                    "theta": self._calculate_theta(underlying_price, strike, exp_date),
                    "vega": self._calculate_vega(underlying_price, strike, exp_date)
                })

                puts.append({
                    "strike": float(strike),
                    "bid": float(put_price * Decimal('0.98')),
                    "ask": float(put_price * Decimal('1.02')),
                    "last": float(put_price),
                    "volume": random.randint(0, 1000),
                    "open_interest": random.randint(0, 5000),
                    "implied_volatility": float(underlying_data.volatility) + random.uniform(-0.05, 0.05),
                    "delta": self._calculate_delta(underlying_price, strike, exp_date, "put"),
                    "gamma": self._calculate_gamma(underlying_price, strike, exp_date),
                    "theta": self._calculate_theta(underlying_price, strike, exp_date),
                    "vega": self._calculate_vega(underlying_price, strike, exp_date)
                })

            chain_data["expirations"].append({
                "expiration_date": exp_date.date().isoformat(),
                "days_to_expiration": (exp_date - datetime.utcnow()).days,
                "calls": calls,
                "puts": puts
            })

        return chain_data

    def _generate_option_expirations(self) -> List[datetime]:
        """Generate realistic option expiration dates."""
        expirations = []
        base_date = datetime.utcnow()

        # Weekly expirations (next 4 weeks)
        for weeks in range(1, 5):
            exp_date = base_date + timedelta(weeks=weeks)
            # Find Friday
            days_to_friday = (4 - exp_date.weekday()) % 7
            friday = exp_date + timedelta(days=days_to_friday)
            expirations.append(friday.replace(hour=16, minute=0, second=0, microsecond=0))

        # Monthly expirations (next 12 months)
        for months in range(1, 13):
            year = base_date.year
            month = base_date.month + months
            if month > 12:
                year += 1
                month -= 12

            # Third Friday of the month
            first_day = datetime(year, month, 1)
            first_friday = first_day + timedelta(days=(4 - first_day.weekday()) % 7)
            third_friday = first_friday + timedelta(weeks=2)
            expirations.append(third_friday.replace(hour=16, minute=0, second=0, microsecond=0))

        return sorted(set(expirations))

    def _generate_option_strikes(self, underlying_price: Decimal) -> List[Decimal]:
        """Generate realistic option strikes around underlying price."""
        strikes = []
        strike_interval = self._get_strike_interval(underlying_price)

        # Generate strikes from 20% below to 20% above underlying
        start_price = underlying_price * Decimal('0.8')
        end_price = underlying_price * Decimal('1.2')

        current_strike = (start_price // strike_interval) * strike_interval
        while current_strike <= end_price:
            strikes.append(current_strike)
            current_strike += strike_interval

        return strikes

    def _get_strike_interval(self, price: Decimal) -> Decimal:
        """Get appropriate strike interval based on underlying price."""
        if price < 25:
            return Decimal('2.5')
        elif price < 50:
            return Decimal('5')
        elif price < 200:
            return Decimal('10')
        else:
            return Decimal('25')

    def _calculate_option_prices(
        self,
        underlying_price: Decimal,
        strike: Decimal,
        expiration: datetime,
        volatility: Decimal
    ) -> Tuple[Decimal, Decimal]:
        """Calculate call and put prices using simplified Black-Scholes."""
        S = float(underlying_price)
        K = float(strike)
        T = max((expiration - datetime.utcnow()).days / 365.0, 0.001)
        r = 0.05  # 5% risk-free rate
        sigma = float(volatility)

        # Simplified Black-Scholes
        from math import log, sqrt, exp
        from scipy.stats import norm

        d1 = (log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*sqrt(T))
        d2 = d1 - sigma*sqrt(T)

        call_price = S*norm.cdf(d1) - K*exp(-r*T)*norm.cdf(d2)
        put_price = K*exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)

        return Decimal(str(max(call_price, 0.01))), Decimal(str(max(put_price, 0.01)))

    def _calculate_delta(self, underlying_price: Decimal, strike: Decimal, expiration: datetime, option_type: str) -> float:
        """Calculate option delta."""
        # Simplified delta calculation
        S = float(underlying_price)
        K = float(strike)
        T = max((expiration - datetime.utcnow()).days / 365.0, 0.001)

        if option_type == "call":
            if S > K:
                return min(0.9, 0.5 + (S - K) / (2 * K))
            else:
                return max(0.1, 0.5 - (K - S) / (2 * K))
        else:  # put
            if S < K:
                return max(-0.9, -0.5 - (K - S) / (2 * K))
            else:
                return min(-0.1, -0.5 + (S - K) / (2 * K))

    def _calculate_gamma(self, underlying_price: Decimal, strike: Decimal, expiration: datetime) -> float:
        """Calculate option gamma."""
        # Simplified gamma - highest at-the-money
        S = float(underlying_price)
        K = float(strike)
        T = max((expiration - datetime.utcnow()).days / 365.0, 0.001)

        moneyness = abs(S - K) / K
        max_gamma = 0.1 / sqrt(T)
        return max_gamma * exp(-5 * moneyness**2)

    def _calculate_theta(self, underlying_price: Decimal, strike: Decimal, expiration: datetime) -> float:
        """Calculate option theta (time decay)."""
        T = max((expiration - datetime.utcnow()).days / 365.0, 0.001)
        S = float(underlying_price)
        K = float(strike)

        # Theta increases as expiration approaches
        base_theta = -0.02 / sqrt(T)
        moneyness_factor = 1 - abs(S - K) / (S + K)  # Higher for ATM options
        return base_theta * moneyness_factor

    def _calculate_vega(self, underlying_price: Decimal, strike: Decimal, expiration: datetime) -> float:
        """Calculate option vega (volatility sensitivity)."""
        T = max((expiration - datetime.utcnow()).days / 365.0, 0.001)
        S = float(underlying_price)
        K = float(strike)

        # Vega highest for ATM options with more time
        moneyness = abs(S - K) / K
        base_vega = 0.2 * sqrt(T)
        return base_vega * exp(-2 * moneyness**2)


# Factory function
async def get_sandbox_market_data_service() -> SandboxMarketDataService:
    """Get sandbox market data service instance."""
    async with get_async_session() as session:
        return SandboxMarketDataService(session)