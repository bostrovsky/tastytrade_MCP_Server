"""Market data and symbol search service for TastyTrade API operations."""
from datetime import datetime
from typing import Any, Dict, List

import httpx

from tastytrade_mcp.models.auth import BrokerLink
from tastytrade_mcp.services.base_service import BaseTastyTradeService
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class MarketDataService(BaseTastyTradeService):
    """Service for market data and symbol search operations."""

    async def search_symbols(
        self, broker_link: BrokerLink, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for tradable symbols.

        Args:
            broker_link: User's broker link with OAuth tokens
            query: Search query
            limit: Maximum results

        Returns:
            List of symbol dictionaries
        """
        client = await self._get_client(broker_link)

        try:
            response = await client.get(
                "/symbols/search",
                params={"symbol": query, "limit": limit}
            )
            response.raise_for_status()

            data = response.json()
            symbols = data.get("data", {}).get("items", [])

            logger.info(f"Found {len(symbols)} symbols for query '{query}'")
            return symbols

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error searching symbols: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error searching symbols: {e}", exc_info=True)
            raise

    async def search_symbols_advanced(
        self,
        broker_link: BrokerLink,
        query: str,
        limit: int = 10,
        asset_types: List[str] = None,
        min_price: float = None,
        max_price: float = None,
        options_enabled: bool = None
    ) -> List[Dict[str, Any]]:
        """
        Advanced search for tradable symbols with filtering capabilities.

        Args:
            broker_link: User's broker link with OAuth tokens
            query: Search query
            limit: Maximum results
            asset_types: Filter by asset types (equity, etf, index, etc.)
            min_price: Minimum stock price filter
            max_price: Maximum stock price filter
            options_enabled: Filter for symbols with options trading

        Returns:
            List of symbol dictionaries with enhanced data
        """
        client = await self._get_client(broker_link)

        try:
            # Start with basic symbol search
            params = {"symbol": query, "limit": limit * 2}  # Get more to filter

            response = await client.get("/symbols/search", params=params)
            response.raise_for_status()

            data = response.json()
            symbols = data.get("data", {}).get("items", [])

            # Apply filters
            filtered_symbols = []
            for symbol in symbols:
                # Asset type filter
                if asset_types:
                    symbol_type = symbol.get('instrument-type', '').lower()
                    if symbol_type not in [t.lower() for t in asset_types]:
                        continue

                # Price filters - get market data for more accurate filtering
                if min_price is not None or max_price is not None or options_enabled is not None:
                    try:
                        # Get current quote for price and options info
                        quote_response = await client.get(f"/market-data/quotes",
                                                        params={"symbols": symbol.get('symbol', '')})
                        quote_response.raise_for_status()
                        quote_data = quote_response.json()

                        if quote_data.get('data'):
                            quote = quote_data['data'][0]
                            current_price = quote.get('last', 0)

                            # Price range filter
                            if min_price is not None and current_price < min_price:
                                continue
                            if max_price is not None and current_price > max_price:
                                continue

                            # Options enabled filter
                            if options_enabled is not None:
                                has_options = quote.get('has-options', False)
                                if options_enabled and not has_options:
                                    continue
                                if not options_enabled and has_options:
                                    continue

                            # Add current price to symbol data
                            symbol['current_price'] = current_price
                            symbol['has_options'] = has_options

                    except Exception as e:
                        logger.warning(f"Could not get market data for {symbol.get('symbol')}: {e}")
                        # Continue without price filtering for this symbol
                        pass

                filtered_symbols.append(symbol)

                # Stop once we have enough results
                if len(filtered_symbols) >= limit:
                    break

            logger.info(f"Found {len(filtered_symbols)} symbols matching filters for query '{query}'")
            return filtered_symbols

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error in advanced symbol search: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error in advanced symbol search: {e}", exc_info=True)
            raise

    async def get_market_data(
        self, broker_link: BrokerLink, symbols: List[str]
    ) -> Dict[str, Any]:
        """
        Get market data for symbols.

        Args:
            broker_link: User's broker link with OAuth tokens
            symbols: List of symbols to get quotes for

        Returns:
            Market data dictionary
        """
        client = await self._get_client(broker_link)

        try:
            # Join symbols for query
            symbols_str = ",".join(symbols)

            response = await client.get(
                f"/market-data/quotes",
                params={"symbols": symbols_str}
            )
            response.raise_for_status()

            data = response.json()
            quotes = data.get("data", {})

            logger.info(f"Fetched market data for {len(symbols)} symbols")
            return quotes

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching market data: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error fetching market data: {e}", exc_info=True)
            raise

    async def get_historical_data(
        self,
        broker_link: BrokerLink,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        include_extended: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get historical OHLCV data for a symbol.

        Args:
            broker_link: User's broker link with OAuth tokens
            symbol: Trading symbol
            timeframe: Time interval (1min, 5min, 15min, 30min, 1hour, 1day, 1week, 1month)
            start_date: Start date for historical data
            end_date: End date for historical data
            include_extended: Include extended hours data

        Returns:
            List of OHLCV data points
        """
        client = await self._get_client(broker_link)

        try:
            # Map timeframe to API format
            interval_map = {
                "1min": "1m",
                "5min": "5m",
                "15min": "15m",
                "30min": "30m",
                "1hour": "1h",
                "1day": "1d",
                "1week": "1w",
                "1month": "1M"
            }
            interval = interval_map.get(timeframe, "1d")

            params = {
                "symbol": symbol,
                "interval": interval,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "extended_hours": include_extended
            }

            response = await client.get(
                f"/market-data/bars/{symbol}",
                params=params
            )
            response.raise_for_status()

            data = response.json()
            bars = data.get("data", {}).get("items", [])

            logger.info(
                f"Fetched {len(bars)} historical data points for {symbol} "
                f"from {start_date.date()} to {end_date.date()}"
            )
            return bars

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching historical data: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}", exc_info=True)
            raise

    async def get_option_chain(
        self, broker_link: BrokerLink, symbol: str, expiration_date: str = None
    ) -> Dict[str, Any]:
        """
        Get option chain data for a symbol.

        Args:
            broker_link: User's broker link with OAuth tokens
            symbol: Underlying symbol
            expiration_date: Specific expiration date (YYYY-MM-DD format), if None gets all

        Returns:
            Option chain data
        """
        client = await self._get_client(broker_link)

        try:
            url = f"/market-data/option-chains/{symbol}"
            params = {}
            if expiration_date:
                params["expiration"] = expiration_date

            response = await client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            chain_data = data.get("data", {})

            logger.info(f"Fetched option chain for {symbol}")
            return chain_data

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching option chain: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error fetching option chain: {e}", exc_info=True)
            raise

    async def get_option_quote(
        self, broker_link: BrokerLink, option_symbol: str
    ) -> Dict[str, Any]:
        """
        Get real-time quote for an option.

        Args:
            broker_link: User's broker link with OAuth tokens
            option_symbol: Option symbol

        Returns:
            Option quote data
        """
        client = await self._get_client(broker_link)

        try:
            response = await client.get(
                f"/market-data/quotes",
                params={"symbols": option_symbol}
            )
            response.raise_for_status()

            data = response.json()
            quotes = data.get("data", [])

            if quotes:
                logger.info(f"Fetched option quote for {option_symbol}")
                return quotes[0]
            else:
                logger.warning(f"No quote data found for {option_symbol}")
                return {}

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching option quote: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error fetching option quote: {e}", exc_info=True)
            raise