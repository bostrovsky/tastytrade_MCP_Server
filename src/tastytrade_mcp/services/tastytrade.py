"""TastyTrade API service using modular architecture with OAuth tokens."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from tastytrade_mcp.models.auth import BrokerLink
from tastytrade_mcp.services.portfolio_service import PortfolioService
from tastytrade_mcp.services.market_data_service import MarketDataService
from tastytrade_mcp.services.trading_service import TradingService
from tastytrade_mcp.services.options_service import OptionsService
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class TastyTradeService:
    """
    Unified service for interacting with TastyTrade API using OAuth tokens.

    This service acts as a facade that composes specialized service modules
    for different functional areas while maintaining backward compatibility.
    """

    def __init__(self, session: AsyncSession):
        """Initialize TastyTrade service with modular components."""
        self.session = session

        # Initialize specialized service modules
        self.portfolio = PortfolioService(session)
        self.market_data = MarketDataService(session)
        self.trading = TradingService(session)
        self.options = OptionsService(session)

    # Portfolio Service Methods
    async def get_accounts(self, broker_link: BrokerLink) -> List[Dict[str, Any]]:
        """Fetch all accounts for the authenticated user."""
        return await self.portfolio.get_accounts(broker_link)

    async def get_positions(
        self, broker_link: BrokerLink, account_number: str
    ) -> List[Dict[str, Any]]:
        """Fetch positions for a specific account."""
        return await self.portfolio.get_positions(broker_link, account_number)

    async def get_positions_with_greeks(
        self, broker_link: BrokerLink, account_number: str
    ) -> List[Dict[str, Any]]:
        """Fetch positions with enhanced Greek data for options."""
        return await self.portfolio.get_positions_with_greeks(broker_link, account_number)

    async def analyze_portfolio(
        self, broker_link: BrokerLink, account_number: str
    ) -> Dict[str, Any]:
        """Perform comprehensive portfolio analysis including Greeks aggregation."""
        return await self.portfolio.analyze_portfolio(broker_link, account_number)

    async def get_balances(
        self, broker_link: BrokerLink, account_number: str
    ) -> Dict[str, Any]:
        """Fetch balance information for a specific account."""
        return await self.portfolio.get_balances(broker_link, account_number)

    # Market Data Service Methods
    async def search_symbols(
        self, broker_link: BrokerLink, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for tradable symbols."""
        return await self.market_data.search_symbols(broker_link, query, limit)

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
        """Advanced search for tradable symbols with filtering capabilities."""
        return await self.market_data.search_symbols_advanced(
            broker_link, query, limit, asset_types, min_price, max_price, options_enabled
        )

    async def get_market_data(
        self, broker_link: BrokerLink, symbols: List[str]
    ) -> Dict[str, Any]:
        """Get market data for symbols."""
        return await self.market_data.get_market_data(broker_link, symbols)

    async def get_historical_data(
        self,
        broker_link: BrokerLink,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        include_extended: bool = False
    ) -> List[Dict[str, Any]]:
        """Get historical OHLCV data for a symbol."""
        return await self.market_data.get_historical_data(
            broker_link, symbol, timeframe, start_date, end_date, include_extended
        )

    # Trading Service Methods
    async def submit_order(
        self, broker_link: BrokerLink, account_id: str, order_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Submit an order to TastyTrade."""
        return await self.trading.submit_order(broker_link, account_id, order_request)

    async def submit_option_order(
        self, broker_link: BrokerLink, account_id: str, option_order_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Submit an options order to TastyTrade."""
        return await self.trading.submit_option_order(broker_link, account_id, option_order_request)

    async def modify_order(
        self, broker_link: BrokerLink, account_id: str, order_id: str, modifications: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Modify an existing order."""
        return await self.trading.modify_order(broker_link, account_id, order_id, modifications)

    async def cancel_order(
        self, broker_link: BrokerLink, account_id: str, order_id: str
    ) -> bool:
        """Cancel an existing order."""
        return await self.trading.cancel_order(broker_link, account_id, order_id)

    async def get_orders(
        self, broker_link: BrokerLink, account_id: str, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get orders for an account."""
        return await self.trading.get_orders(broker_link, account_id, status)

    async def get_order_status(
        self, broker_link: BrokerLink, account_id: str, order_id: str
    ) -> Dict[str, Any]:
        """Get status of a specific order."""
        return await self.trading.get_order_status(broker_link, account_id, order_id)

    # Options Service Methods
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
        """Scan for trading opportunities based on specified criteria."""
        return await self.options.scan_opportunities(
            broker_link, strategy_type, min_return, max_risk, max_dte, min_volume,
            watchlist_symbols, limit
        )

    async def analyze_option_strategy(
        self,
        broker_link: BrokerLink,
        strategy_legs: List[Dict[str, Any]],
        underlying_price: float
    ) -> Dict[str, Any]:
        """Analyze a multi-leg option strategy."""
        return await self.options.analyze_option_strategy(broker_link, strategy_legs, underlying_price)

    # Service Management Methods
    async def close(self):
        """Close all service connections."""
        await self.portfolio.close()
        await self.market_data.close()
        await self.trading.close()
        await self.options.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()