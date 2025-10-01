"""Trading operations service for TastyTrade API order management."""
from typing import Any, Dict, List, Optional

import httpx

from tastytrade_mcp.models.auth import BrokerLink
from tastytrade_mcp.services.base_service import BaseTastyTradeService
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class TradingService(BaseTastyTradeService):
    """Service for trading operations and order management."""

    async def submit_order(
        self, broker_link: BrokerLink, account_id: str, order_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Submit an order to TastyTrade.

        Args:
            broker_link: User's broker link with OAuth tokens
            account_id: Account to place order for
            order_request: Order details dictionary

        Returns:
            Order response data
        """
        try:
            client = await self._get_client(broker_link)

            # Build order payload for TastyTrade API
            payload = {
                "order-type": order_request["order_type"],
                "time-in-force": order_request.get("time_in_force", "Day"),
                "legs": [
                    {
                        "instrument-type": "Equity",
                        "symbol": order_request["symbol"],
                        "quantity": order_request["quantity"],
                        "action": order_request["side"].title(),  # Buy/Sell
                    }
                ]
            }

            # Add price fields based on order type
            if order_request.get("price"):
                payload["price"] = order_request["price"]
            if order_request.get("stop_price"):
                payload["stop-trigger"] = order_request["stop_price"]

            response = await client.post(
                f"/accounts/{account_id}/orders",
                json=payload
            )

            if response.status_code != 201:
                logger.error(f"Order submission failed: {response.text}")
                raise Exception(f"Failed to submit order: {response.status_code}")

            data = response.json()
            order_data = data.get("data", {})

            logger.info(f"Successfully submitted order for {order_request['symbol']}")
            return order_data

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error submitting order: {e.response.status_code}")
            if await self._handle_api_error(e, broker_link):
                return await self.submit_order(broker_link, account_id, order_request)
            raise
        except Exception as e:
            logger.error(f"Failed to submit order: {e}", exc_info=True)
            raise

    async def submit_option_order(
        self, broker_link: BrokerLink, account_id: str, option_order_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Submit an options order to TastyTrade.

        Args:
            broker_link: User's broker link with OAuth tokens
            account_id: Account to place order for
            option_order_request: Options order details dictionary

        Returns:
            Order response data
        """
        try:
            client = await self._get_client(broker_link)

            # Build options order payload
            legs = []
            for leg in option_order_request.get("legs", []):
                leg_data = {
                    "instrument-type": "Option",
                    "symbol": leg["option_symbol"],
                    "quantity": leg["quantity"],
                    "action": leg["side"].title(),  # Buy/Sell
                }
                legs.append(leg_data)

            payload = {
                "order-type": option_order_request["order_type"],
                "time-in-force": option_order_request.get("time_in_force", "Day"),
                "legs": legs
            }

            # Add price fields for multi-leg orders
            if option_order_request.get("net_debit"):
                payload["price"] = option_order_request["net_debit"]
            elif option_order_request.get("net_credit"):
                payload["price"] = option_order_request["net_credit"]

            response = await client.post(
                f"/accounts/{account_id}/orders",
                json=payload
            )

            if response.status_code != 201:
                logger.error(f"Options order submission failed: {response.text}")
                raise Exception(f"Failed to submit options order: {response.status_code}")

            data = response.json()
            order_data = data.get("data", {})

            logger.info(f"Successfully submitted options order with {len(legs)} legs")
            return order_data

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error submitting options order: {e.response.status_code}")
            if await self._handle_api_error(e, broker_link):
                return await self.submit_option_order(broker_link, account_id, option_order_request)
            raise
        except Exception as e:
            logger.error(f"Failed to submit options order: {e}", exc_info=True)
            raise

    async def modify_order(
        self, broker_link: BrokerLink, account_id: str, order_id: str, modifications: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Modify an existing order.

        Args:
            broker_link: User's broker link with OAuth tokens
            account_id: Account the order belongs to
            order_id: ID of order to modify
            modifications: Changes to apply to the order

        Returns:
            Modified order data
        """
        try:
            client = await self._get_client(broker_link)

            payload = {}
            if modifications.get("price"):
                payload["price"] = modifications["price"]
            if modifications.get("quantity"):
                payload["quantity"] = modifications["quantity"]

            response = await client.put(
                f"/accounts/{account_id}/orders/{order_id}",
                json=payload
            )

            if response.status_code != 200:
                logger.error(f"Order modification failed: {response.text}")
                raise Exception(f"Failed to modify order: {response.status_code}")

            data = response.json()
            order_data = data.get("data", {})

            logger.info(f"Successfully modified order {order_id}")
            return order_data

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error modifying order: {e.response.status_code}")
            if await self._handle_api_error(e, broker_link):
                return await self.modify_order(broker_link, account_id, order_id, modifications)
            raise
        except Exception as e:
            logger.error(f"Failed to modify order: {e}", exc_info=True)
            raise

    async def cancel_order(
        self, broker_link: BrokerLink, account_id: str, order_id: str
    ) -> bool:
        """
        Cancel an existing order.

        Args:
            broker_link: User's broker link with OAuth tokens
            account_id: Account the order belongs to
            order_id: ID of order to cancel

        Returns:
            True if cancellation successful
        """
        try:
            client = await self._get_client(broker_link)

            response = await client.delete(
                f"/accounts/{account_id}/orders/{order_id}"
            )

            if response.status_code not in [200, 204]:
                logger.error(f"Order cancellation failed: {response.text}")
                raise Exception(f"Failed to cancel order: {response.status_code}")

            logger.info(f"Successfully cancelled order {order_id}")
            return True

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error cancelling order: {e.response.status_code}")
            if await self._handle_api_error(e, broker_link):
                return await self.cancel_order(broker_link, account_id, order_id)
            raise
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}", exc_info=True)
            raise

    async def get_orders(
        self, broker_link: BrokerLink, account_id: str, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get orders for an account.

        Args:
            broker_link: User's broker link with OAuth tokens
            account_id: Account to get orders for
            status: Filter by order status (optional)

        Returns:
            List of order dictionaries
        """
        try:
            client = await self._get_client(broker_link)

            params = {}
            if status:
                params["status"] = status

            response = await client.get(
                f"/accounts/{account_id}/orders",
                params=params
            )

            if response.status_code != 200:
                logger.error(f"Failed to get orders: {response.text}")
                raise Exception(f"Failed to get orders: {response.status_code}")

            data = response.json()
            orders = data.get("data", {}).get("items", [])

            logger.info(f"Fetched {len(orders)} orders for account {account_id}")
            return orders

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting orders: {e.response.status_code}")
            if await self._handle_api_error(e, broker_link):
                return await self.get_orders(broker_link, account_id, status)
            raise
        except Exception as e:
            logger.error(f"Failed to get orders: {e}", exc_info=True)
            raise

    async def get_order_status(
        self, broker_link: BrokerLink, account_id: str, order_id: str
    ) -> Dict[str, Any]:
        """
        Get status of a specific order.

        Args:
            broker_link: User's broker link with OAuth tokens
            account_id: Account the order belongs to
            order_id: ID of order to check

        Returns:
            Order status data
        """
        try:
            client = await self._get_client(broker_link)

            response = await client.get(
                f"/accounts/{account_id}/orders/{order_id}"
            )

            if response.status_code != 200:
                logger.error(f"Failed to get order status: {response.text}")
                raise Exception(f"Failed to get order status: {response.status_code}")

            data = response.json()
            order_data = data.get("data", {})

            logger.info(f"Fetched status for order {order_id}")
            return order_data

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting order status: {e.response.status_code}")
            if await self._handle_api_error(e, broker_link):
                return await self.get_order_status(broker_link, account_id, order_id)
            raise
        except Exception as e:
            logger.error(f"Failed to get order status: {e}", exc_info=True)
            raise