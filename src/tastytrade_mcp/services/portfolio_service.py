"""Portfolio management service for TastyTrade API operations."""
from datetime import datetime
from typing import Any, Dict, List

import httpx

from tastytrade_mcp.models.auth import BrokerLink
from tastytrade_mcp.services.base_service import BaseTastyTradeService
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class PortfolioService(BaseTastyTradeService):
    """Service for portfolio and account management operations."""

    async def get_accounts(self, broker_link: BrokerLink) -> List[Dict[str, Any]]:
        """
        Fetch all accounts for the authenticated user.

        Args:
            broker_link: User's broker link with OAuth tokens

        Returns:
            List of account dictionaries
        """
        client = await self._get_client(broker_link)

        try:
            response = await client.get("/accounts")
            response.raise_for_status()

            data = response.json()
            accounts = data.get("data", {}).get("items", [])

            logger.info(f"Fetched {len(accounts)} accounts for broker_link {broker_link.id}")
            return accounts

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching accounts: {e.response.status_code}")
            if await self._handle_api_error(e, broker_link):
                return await self.get_accounts(broker_link)
            raise
        except Exception as e:
            logger.error(f"Error fetching accounts: {e}", exc_info=True)
            raise

    async def get_positions(
        self, broker_link: BrokerLink, account_number: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch positions for a specific account.

        Args:
            broker_link: User's broker link with OAuth tokens
            account_number: Account to fetch positions for

        Returns:
            List of position dictionaries
        """
        client = await self._get_client(broker_link)

        try:
            response = await client.get(f"/accounts/{account_number}/positions")
            response.raise_for_status()

            data = response.json()
            positions = data.get("data", {}).get("items", [])

            logger.info(
                f"Fetched {len(positions)} positions for account {account_number}"
            )
            return positions

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching positions: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error fetching positions: {e}", exc_info=True)
            raise

    async def get_positions_with_greeks(
        self, broker_link: BrokerLink, account_number: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch positions with enhanced Greek data for options.

        Args:
            broker_link: User's broker link with OAuth tokens
            account_number: Account to fetch positions for

        Returns:
            List of position dictionaries with Greek data
        """
        client = await self._get_client(broker_link)

        try:
            # Get basic positions
            positions = await self.get_positions(broker_link, account_number)

            # Enhance option positions with Greeks data
            enhanced_positions = []
            for position in positions:
                enhanced_position = position.copy()

                # Check if this is an option position
                instrument = position.get('instrument', {})
                instrument_type = instrument.get('instrument-type', '')

                if instrument_type.upper() in ['OPTION', 'OPTIONS']:
                    # For options, try to get Greeks data
                    symbol = instrument.get('symbol', '')
                    if symbol:
                        try:
                            # Try to get option data with Greeks
                            greeks_data = await self._get_option_greeks(client, symbol)
                            if greeks_data:
                                enhanced_position['greeks'] = greeks_data
                        except Exception as e:
                            logger.warning(f"Could not fetch Greeks for {symbol}: {e}")
                            # Add placeholder Greeks data
                            enhanced_position['greeks'] = {
                                'delta': None,
                                'gamma': None,
                                'theta': None,
                                'vega': None,
                                'rho': None,
                                'implied_volatility': None,
                                'time_value': None,
                                'intrinsic_value': None
                            }

                enhanced_positions.append(enhanced_position)

            logger.info(
                f"Fetched {len(enhanced_positions)} enhanced positions for account {account_number}"
            )
            return enhanced_positions

        except Exception as e:
            logger.error(f"Error fetching enhanced positions: {e}", exc_info=True)
            raise

    async def _get_option_greeks(self, client, symbol: str) -> Dict[str, Any]:
        """
        Fetch Greeks data for a specific option symbol.

        Args:
            client: HTTP client with auth
            symbol: Option symbol

        Returns:
            Dictionary with Greeks data
        """
        try:
            # Try to get option data - TastyTrade may have Greeks in option details
            response = await client.get(f"/instruments/options/{symbol}")
            response.raise_for_status()

            data = response.json()
            option_data = data.get("data", {})

            # Extract Greeks if available
            greeks = {}

            # Try different possible field names for Greeks
            for greek in ['delta', 'gamma', 'theta', 'vega', 'rho']:
                greeks[greek] = option_data.get(greek) or option_data.get(f'{greek}_value')

            # Try to get IV and time/intrinsic values
            greeks['implied_volatility'] = option_data.get('implied_volatility') or option_data.get('iv')
            greeks['time_value'] = option_data.get('time_value')
            greeks['intrinsic_value'] = option_data.get('intrinsic_value')

            return greeks

        except Exception as e:
            logger.debug(f"Could not fetch option details for {symbol}: {e}")
            return {}

    async def get_balances(
        self, broker_link: BrokerLink, account_number: str
    ) -> Dict[str, Any]:
        """
        Fetch balance information for a specific account.

        Args:
            broker_link: User's broker link with OAuth tokens
            account_number: Account to fetch balances for

        Returns:
            Balance dictionary
        """
        client = await self._get_client(broker_link)

        try:
            response = await client.get(f"/accounts/{account_number}/balances")
            response.raise_for_status()

            data = response.json()
            balances = data.get("data", {})

            logger.info(f"Fetched balances for account {account_number}")
            return balances

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching balances: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Error fetching balances: {e}", exc_info=True)
            raise

    async def analyze_portfolio(
        self, broker_link: BrokerLink, account_number: str
    ) -> Dict[str, Any]:
        """
        Perform comprehensive portfolio analysis including Greeks aggregation.

        Args:
            broker_link: User's broker link with OAuth tokens
            account_number: Account to analyze

        Returns:
            Dictionary with portfolio analysis data
        """
        try:
            # Get enhanced positions data
            positions = await self.get_positions_with_greeks(broker_link, account_number)
            balances = await self.get_balances(broker_link, account_number)

            # Initialize analysis data
            analysis = {
                "account_number": account_number,
                "timestamp": datetime.utcnow().isoformat(),
                "position_count": len(positions),
                "portfolio_summary": {},
                "greeks_analysis": {},
                "risk_metrics": {},
                "asset_allocation": {},
                "options_analysis": {}
            }

            # Portfolio summary calculations
            total_market_value = 0
            total_unrealized_pnl = 0
            equity_value = 0
            options_value = 0

            # Greeks aggregation
            portfolio_greeks = {
                "total_delta": 0,
                "total_gamma": 0,
                "total_theta": 0,
                "total_vega": 0,
                "total_rho": 0
            }

            # Options analysis
            option_positions = []
            equity_positions = []

            for position in positions:
                market_value = position.get('market-value', 0)
                unrealized_pnl = position.get('unrealized-p-l', 0)
                quantity = position.get('quantity', 0)

                total_market_value += market_value
                total_unrealized_pnl += unrealized_pnl

                # Check if this is an option position
                instrument = position.get('instrument', {})
                instrument_type = instrument.get('instrument-type', '').upper()

                if instrument_type in ['OPTION', 'OPTIONS']:
                    options_value += market_value
                    option_positions.append(position)

                    # Aggregate Greeks
                    greeks = position.get('greeks', {})
                    if greeks:
                        delta = greeks.get('delta', 0) or 0
                        gamma = greeks.get('gamma', 0) or 0
                        theta = greeks.get('theta', 0) or 0
                        vega = greeks.get('vega', 0) or 0
                        rho = greeks.get('rho', 0) or 0

                        # Calculate position Greeks
                        portfolio_greeks["total_delta"] += delta * quantity
                        portfolio_greeks["total_gamma"] += gamma * quantity
                        portfolio_greeks["total_theta"] += theta * quantity
                        portfolio_greeks["total_vega"] += vega * quantity
                        portfolio_greeks["total_rho"] += rho * quantity
                else:
                    equity_value += market_value
                    equity_positions.append(position)

            # Portfolio summary
            analysis["portfolio_summary"] = {
                "total_market_value": total_market_value,
                "total_unrealized_pnl": total_unrealized_pnl,
                "unrealized_pnl_percent": (total_unrealized_pnl / total_market_value * 100) if total_market_value > 0 else 0,
                "net_liquidating_value": balances.get('net-liquidating-value', 0),
                "buying_power": balances.get('buying-power', 0),
                "cash_balance": balances.get('cash-balance', 0)
            }

            # Greeks analysis
            analysis["greeks_analysis"] = {
                **portfolio_greeks,
                "delta_dollars": portfolio_greeks["total_delta"] * 100,  # Delta in $ per $1 move in underlying
                "theta_dollars_per_day": portfolio_greeks["total_theta"],  # Theta decay in $ per day
                "vega_per_vol_point": portfolio_greeks["total_vega"],  # Vega sensitivity per 1% vol change
                "option_count": len(option_positions)
            }

            # Asset allocation
            analysis["asset_allocation"] = {
                "equities_value": equity_value,
                "options_value": options_value,
                "equities_percent": (equity_value / total_market_value * 100) if total_market_value > 0 else 0,
                "options_percent": (options_value / total_market_value * 100) if total_market_value > 0 else 0,
                "equity_positions": len(equity_positions),
                "option_positions": len(option_positions)
            }

            # Risk metrics
            analysis["risk_metrics"] = {
                "portfolio_delta": portfolio_greeks["total_delta"],
                "delta_exposure_percent": abs(portfolio_greeks["total_delta"] * 100 / total_market_value) if total_market_value > 0 else 0,
                "daily_theta_decay": portfolio_greeks["total_theta"],
                "theta_decay_percent": abs(portfolio_greeks["total_theta"] / total_market_value * 100) if total_market_value > 0 else 0,
                "volatility_exposure": portfolio_greeks["total_vega"],
                "largest_position_percent": max([abs(pos.get('market-value', 0)) / total_market_value * 100 for pos in positions]) if positions and total_market_value > 0 else 0
            }

            # Options-specific analysis
            if option_positions:
                # Group by underlying
                by_underlying = {}
                for pos in option_positions:
                    symbol = pos.get('symbol', '')
                    underlying = symbol.split()[0] if symbol else 'Unknown'  # Extract underlying from option symbol

                    if underlying not in by_underlying:
                        by_underlying[underlying] = {
                            "positions": [],
                            "total_delta": 0,
                            "total_value": 0
                        }

                    by_underlying[underlying]["positions"].append(pos)
                    by_underlying[underlying]["total_value"] += pos.get('market-value', 0)

                    greeks = pos.get('greeks', {})
                    if greeks and greeks.get('delta'):
                        by_underlying[underlying]["total_delta"] += greeks.get('delta', 0) * pos.get('quantity', 0)

                analysis["options_analysis"] = {
                    "by_underlying": by_underlying,
                    "total_underlyings": len(by_underlying)
                }

            logger.info(f"Completed portfolio analysis for account {account_number}")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing portfolio: {e}", exc_info=True)
            raise