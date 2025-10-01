"""Options analysis and scanning service for TastyTrade API operations."""
from datetime import datetime
from typing import Any, Dict, List

import httpx

from tastytrade_mcp.models.auth import BrokerLink
from tastytrade_mcp.services.base_service import BaseTastyTradeService
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class OptionsService(BaseTastyTradeService):
    """Service for options analysis and opportunity scanning."""

    async def scan_opportunities(
        self,
        broker_link: BrokerLink,
        strategy_type: str = "covered_call",
        min_return: float = None,
        max_risk: float = None,
        max_dte: int = 45,
        min_volume: int = 100,
        watchlist_symbols: List[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Scan for trading opportunities based on specified criteria.

        Args:
            broker_link: User's broker link with OAuth tokens
            strategy_type: Type of strategy to scan for (covered_call, cash_secured_put, etc.)
            min_return: Minimum return percentage required
            max_risk: Maximum risk amount per trade
            max_dte: Maximum days to expiration
            min_volume: Minimum option volume
            watchlist_symbols: List of symbols to scan (if None, uses popular options symbols)
            limit: Maximum results to return

        Returns:
            List of trading opportunity dictionaries
        """
        client = await self._get_client(broker_link)

        try:
            # Default watchlist if none provided
            if not watchlist_symbols:
                watchlist_symbols = [
                    "AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "NVDA", "META", "NFLX",
                    "SPY", "QQQ", "IWM", "XLE", "XLF", "XLK", "XLV", "AMD", "PLTR"
                ]

            opportunities = []

            for symbol in watchlist_symbols:
                try:
                    # Get current stock quote
                    quote_response = await client.get(f"/market-data/quotes",
                                                    params={"symbols": symbol})
                    quote_response.raise_for_status()
                    quote_data = quote_response.json()

                    if not quote_data.get('data'):
                        continue

                    stock_quote = quote_data['data'][0]
                    stock_price = stock_quote.get('last', 0)

                    if not stock_price:
                        continue

                    # Get option chain
                    chain_response = await client.get(f"/market-data/option-chains/{symbol}")
                    chain_response.raise_for_status()
                    chain_data = chain_response.json()

                    if not chain_data.get('data', {}).get('items'):
                        continue

                    # Process options based on strategy type
                    if strategy_type == "covered_call":
                        opportunities.extend(
                            await self._scan_covered_calls(
                                symbol, stock_price, chain_data, max_dte, min_volume, min_return, client
                            )
                        )
                    elif strategy_type == "cash_secured_put":
                        opportunities.extend(
                            await self._scan_cash_secured_puts(
                                symbol, stock_price, chain_data, max_dte, min_volume, min_return, client
                            )
                        )
                    elif strategy_type == "strangles":
                        opportunities.extend(
                            await self._scan_strangles(
                                symbol, stock_price, chain_data, max_dte, min_volume, min_return, max_risk, client
                            )
                        )

                except Exception as e:
                    logger.warning(f"Error scanning {symbol}: {e}")
                    continue

                # Stop if we have enough results
                if len(opportunities) >= limit:
                    break

            # Sort by return/risk ratio or other criteria
            opportunities.sort(key=lambda x: x.get('return_percent', 0), reverse=True)

            logger.info(f"Found {len(opportunities)} trading opportunities")
            return opportunities[:limit]

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error in opportunity scan: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error in opportunity scan: {e}", exc_info=True)
            raise

    async def _scan_covered_calls(
        self, symbol: str, stock_price: float, chain_data: dict, max_dte: int,
        min_volume: int, min_return: float, client
    ) -> List[Dict[str, Any]]:
        """Scan for covered call opportunities."""
        opportunities = []

        for expiration in chain_data.get('data', {}).get('items', []):
            exp_date = expiration.get('expiration-date')
            if not exp_date:
                continue

            # Calculate DTE
            exp_datetime = datetime.fromisoformat(exp_date.replace('Z', '+00:00'))
            dte = (exp_datetime.date() - datetime.now().date()).days

            if dte > max_dte or dte < 1:
                continue

            # Look at call options (for covered calls, we sell calls)
            for strike_data in expiration.get('strikes', []):
                call_option = strike_data.get('call')
                if not call_option:
                    continue

                strike = float(strike_data.get('strike-price', 0))

                # For covered calls, typically sell OTM calls
                if strike <= stock_price:
                    continue

                bid = call_option.get('bid', 0)
                volume = call_option.get('total-volume', 0)

                if bid <= 0 or volume < min_volume:
                    continue

                # Calculate return
                premium = bid
                max_profit = premium + (strike - stock_price)
                return_percent = (max_profit / stock_price) * 100

                if min_return and return_percent < min_return:
                    continue

                opportunities.append({
                    'strategy': 'covered_call',
                    'symbol': symbol,
                    'stock_price': stock_price,
                    'strike': strike,
                    'expiration': exp_date,
                    'dte': dte,
                    'premium': premium,
                    'return_percent': return_percent,
                    'max_profit': max_profit,
                    'volume': volume,
                    'option_symbol': call_option.get('symbol', ''),
                })

        return opportunities

    async def _scan_cash_secured_puts(
        self, symbol: str, stock_price: float, chain_data: dict, max_dte: int,
        min_volume: int, min_return: float, client
    ) -> List[Dict[str, Any]]:
        """Scan for cash secured put opportunities."""
        opportunities = []

        for expiration in chain_data.get('data', {}).get('items', []):
            exp_date = expiration.get('expiration-date')
            if not exp_date:
                continue

            exp_datetime = datetime.fromisoformat(exp_date.replace('Z', '+00:00'))
            dte = (exp_datetime.date() - datetime.now().date()).days

            if dte > max_dte or dte < 1:
                continue

            for strike_data in expiration.get('strikes', []):
                put_option = strike_data.get('put')
                if not put_option:
                    continue

                strike = float(strike_data.get('strike-price', 0))

                # For CSPs, typically sell OTM puts
                if strike >= stock_price:
                    continue

                bid = put_option.get('bid', 0)
                volume = put_option.get('total-volume', 0)

                if bid <= 0 or volume < min_volume:
                    continue

                # Calculate return (premium received / cash required)
                cash_required = strike * 100  # Per contract
                return_percent = (bid * 100 / cash_required) * 100

                if min_return and return_percent < min_return:
                    continue

                opportunities.append({
                    'strategy': 'cash_secured_put',
                    'symbol': symbol,
                    'stock_price': stock_price,
                    'strike': strike,
                    'expiration': exp_date,
                    'dte': dte,
                    'premium': bid,
                    'return_percent': return_percent,
                    'cash_required': cash_required,
                    'volume': volume,
                    'option_symbol': put_option.get('symbol', ''),
                })

        return opportunities

    async def _scan_strangles(
        self, symbol: str, stock_price: float, chain_data: dict, max_dte: int,
        min_volume: int, min_return: float, max_risk: float, client
    ) -> List[Dict[str, Any]]:
        """Scan for strangle opportunities."""
        opportunities = []

        for expiration in chain_data.get('data', {}).get('items', []):
            exp_date = expiration.get('expiration-date')
            if not exp_date:
                continue

            exp_datetime = datetime.fromisoformat(exp_date.replace('Z', '+00:00'))
            dte = (exp_datetime.date() - datetime.now().date()).days

            if dte > max_dte or dte < 1:
                continue

            # Find OTM put and call pairs
            puts = []
            calls = []

            for strike_data in expiration.get('strikes', []):
                strike = float(strike_data.get('strike-price', 0))

                put_option = strike_data.get('put')
                call_option = strike_data.get('call')

                if put_option and strike < stock_price:
                    bid = put_option.get('bid', 0)
                    volume = put_option.get('total-volume', 0)
                    if bid > 0 and volume >= min_volume:
                        puts.append({
                            'strike': strike,
                            'bid': bid,
                            'volume': volume,
                            'symbol': put_option.get('symbol', '')
                        })

                if call_option and strike > stock_price:
                    bid = call_option.get('bid', 0)
                    volume = call_option.get('total-volume', 0)
                    if bid > 0 and volume >= min_volume:
                        calls.append({
                            'strike': strike,
                            'bid': bid,
                            'volume': volume,
                            'symbol': call_option.get('symbol', '')
                        })

            # Create strangle combinations
            for put in puts:
                for call in calls:
                    total_premium = put['bid'] + call['bid']
                    total_risk = max_risk if max_risk else total_premium * 100 * 10  # Default max risk

                    if max_risk and total_premium * 100 > max_risk:
                        continue

                    return_percent = (total_premium / (total_premium * 10)) * 100  # Rough estimate

                    if min_return and return_percent < min_return:
                        continue

                    opportunities.append({
                        'strategy': 'strangle',
                        'symbol': symbol,
                        'stock_price': stock_price,
                        'put_strike': put['strike'],
                        'call_strike': call['strike'],
                        'expiration': exp_date,
                        'dte': dte,
                        'total_premium': total_premium,
                        'return_percent': return_percent,
                        'put_volume': put['volume'],
                        'call_volume': call['volume'],
                        'put_symbol': put['symbol'],
                        'call_symbol': call['symbol'],
                    })

        return opportunities

    async def analyze_option_strategy(
        self,
        broker_link: BrokerLink,
        strategy_legs: List[Dict[str, Any]],
        underlying_price: float
    ) -> Dict[str, Any]:
        """
        Analyze a multi-leg option strategy.

        Args:
            broker_link: User's broker link with OAuth tokens
            strategy_legs: List of option legs with symbols and quantities
            underlying_price: Current price of underlying

        Returns:
            Strategy analysis data
        """
        client = await self._get_client(broker_link)

        try:
            analysis = {
                "strategy_type": "custom",
                "legs": [],
                "profit_loss": {},
                "greeks": {},
                "breakeven_points": [],
                "max_profit": None,
                "max_loss": None,
                "underlying_price": underlying_price
            }

            total_delta = 0
            total_gamma = 0
            total_theta = 0
            total_vega = 0
            total_cost = 0

            # Analyze each leg
            for leg in strategy_legs:
                try:
                    # Get option quote and Greeks
                    quote_response = await client.get(
                        f"/market-data/quotes",
                        params={"symbols": leg["option_symbol"]}
                    )
                    quote_response.raise_for_status()
                    quote_data = quote_response.json()

                    if not quote_data.get('data'):
                        continue

                    option_quote = quote_data['data'][0]

                    # Calculate leg cost/credit
                    if leg["side"].lower() == "buy":
                        leg_cost = option_quote.get('ask', 0) * leg["quantity"] * 100
                        total_cost += leg_cost
                    else:  # sell
                        leg_credit = option_quote.get('bid', 0) * leg["quantity"] * 100
                        total_cost -= leg_credit

                    # Get Greeks (if available)
                    delta = option_quote.get('delta', 0) or 0
                    gamma = option_quote.get('gamma', 0) or 0
                    theta = option_quote.get('theta', 0) or 0
                    vega = option_quote.get('vega', 0) or 0

                    # Apply position multiplier
                    position_multiplier = leg["quantity"] if leg["side"].lower() == "buy" else -leg["quantity"]

                    total_delta += delta * position_multiplier
                    total_gamma += gamma * position_multiplier
                    total_theta += theta * position_multiplier
                    total_vega += vega * position_multiplier

                    leg_analysis = {
                        "option_symbol": leg["option_symbol"],
                        "side": leg["side"],
                        "quantity": leg["quantity"],
                        "current_price": option_quote.get('last', 0),
                        "bid": option_quote.get('bid', 0),
                        "ask": option_quote.get('ask', 0),
                        "delta": delta,
                        "gamma": gamma,
                        "theta": theta,
                        "vega": vega,
                        "strike": leg.get("strike"),
                        "expiration": leg.get("expiration")
                    }
                    analysis["legs"].append(leg_analysis)

                except Exception as e:
                    logger.warning(f"Could not analyze leg {leg.get('option_symbol')}: {e}")
                    continue

            # Portfolio Greeks
            analysis["greeks"] = {
                "delta": total_delta,
                "gamma": total_gamma,
                "theta": total_theta,
                "vega": total_vega,
                "delta_dollars": total_delta * 100,
                "theta_dollars_per_day": total_theta,
                "vega_per_vol_point": total_vega
            }

            # Basic P&L analysis
            analysis["profit_loss"] = {
                "initial_cost": total_cost,
                "current_value": sum([leg.get("current_price", 0) * leg.get("quantity", 0) * 100
                                    * (1 if leg.get("side", "").lower() == "buy" else -1)
                                    for leg in analysis["legs"]]),
                "unrealized_pnl": 0  # Will be calculated based on current vs initial
            }

            logger.info(f"Analyzed {len(analysis['legs'])} leg option strategy")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing option strategy: {e}", exc_info=True)
            raise