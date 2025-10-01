"""Response parser for TastyTrade API responses.

Converts raw JSON API responses into Python objects that match
the existing handler expectations, allowing smooth migration from SDK.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ParsedAccount:
    """Parsed account data from API response."""
    account_number: str
    nickname: Optional[str]
    account_type: str
    opened_at: Optional[datetime]
    is_closed: bool = False
    authority: str = "Owner"

    def __str__(self):
        return f"Account {self.account_number} ({self.nickname or self.account_type})"


@dataclass
class ParsedBalance:
    """Parsed balance data from API response."""
    account_number: str
    cash_balance: float
    net_liquidating_value: float
    buying_power: float
    pending_cash: float
    maintenance_requirement: float
    cash_available_for_trading: float
    cash_available_for_withdrawal: float

    def __str__(self):
        return f"Balance: ${self.net_liquidating_value:,.2f} (Cash: ${self.cash_balance:,.2f})"


@dataclass
class ParsedPosition:
    """Parsed position data from API response."""
    symbol: str
    quantity: int
    average_price: float
    market_value: float
    unrealized_pl: float
    realized_pl: float
    position_type: str
    instrument_type: str
    underlying_symbol: Optional[str] = None

    def __str__(self):
        return f"{self.symbol}: {self.quantity} @ ${self.average_price:.2f}"


@dataclass
class ParsedOrder:
    """Parsed order data from API response."""
    order_id: str
    account_number: str
    symbol: str
    quantity: int
    order_type: str
    side: str
    status: str
    price: Optional[float]
    time_in_force: str
    created_at: datetime
    updated_at: datetime

    def __str__(self):
        return f"Order {self.order_id}: {self.side} {self.quantity} {self.symbol} - {self.status}"


@dataclass
class ParsedQuote:
    """Parsed quote data from API response."""
    symbol: str
    bid_price: float
    ask_price: float
    last_price: float
    bid_size: int
    ask_size: int
    volume: int
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    change: float
    change_percent: float

    def __str__(self):
        return f"{self.symbol}: ${self.last_price:.2f} ({self.change_percent:+.2f}%)"


class ResponseParser:
    """Parse TastyTrade API responses into Python objects."""

    @staticmethod
    def parse_accounts(response: Dict[str, Any]) -> List[ParsedAccount]:
        """Parse accounts response.

        Args:
            response: Raw API response with accounts data

        Returns:
            List of ParsedAccount objects
        """
        accounts = []
        items = response.get("data", {}).get("items", [])

        for item in items:
            try:
                # Account data is nested under 'account' key
                account_data = item.get("account", {})

                # Parse opened-at timestamp
                opened_at = None
                if "opened-at" in account_data:
                    try:
                        opened_at = datetime.fromisoformat(
                            account_data["opened-at"].replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

                accounts.append(ParsedAccount(
                    account_number=account_data["account-number"],
                    nickname=account_data.get("nickname"),
                    account_type=account_data.get("account-type-name", "Unknown"),
                    opened_at=opened_at,
                    is_closed=account_data.get("is-closed", False),
                    authority=item.get("authority-level", "owner")  # This is at the item level
                ))
            except KeyError as e:
                logger.error(f"Error parsing account: {e}")
                continue

        logger.info(f"Parsed {len(accounts)} accounts")
        return accounts

    @staticmethod
    def parse_balances(response: Dict[str, Any], account_number: str = "") -> ParsedBalance:
        """Parse balance response.

        Args:
            response: Raw API response with balance data
            account_number: Account number for reference

        Returns:
            ParsedBalance object
        """
        data = response.get("data", {})

        return ParsedBalance(
            account_number=account_number,
            cash_balance=float(data.get("cash-balance", 0)),
            net_liquidating_value=float(data.get("net-liquidating-value", 0)),
            buying_power=float(data.get("derivative-buying-power", 0)),
            pending_cash=float(data.get("pending-cash", 0)),
            maintenance_requirement=float(data.get("maintenance-requirement", 0)),
            cash_available_for_trading=float(data.get("cash-available-for-trading", 0)),
            cash_available_for_withdrawal=float(data.get("cash-available-for-withdrawal", 0))
        )

    @staticmethod
    def parse_positions(response: Dict[str, Any]) -> List[ParsedPosition]:
        """Parse positions response.

        Args:
            response: Raw API response with positions data

        Returns:
            List of ParsedPosition objects
        """
        positions = []
        items = response.get("data", {}).get("items", [])

        for item in items:
            try:
                positions.append(ParsedPosition(
                    symbol=item["symbol"],
                    quantity=int(item["quantity"]),
                    average_price=float(item.get("average-open-price", 0)),
                    market_value=float(item.get("market-value", 0)),
                    unrealized_pl=float(item.get("unrealized-day-gain", 0)),
                    realized_pl=float(item.get("realized-day-gain", 0)),
                    position_type=item.get("quantity-direction", ""),
                    instrument_type=item.get("instrument-type", ""),
                    underlying_symbol=item.get("underlying-symbol")
                ))
            except (KeyError, ValueError) as e:
                logger.error(f"Error parsing position: {e}")
                continue

        logger.info(f"Parsed {len(positions)} positions")
        return positions

    @staticmethod
    def parse_orders(response: Dict[str, Any]) -> List[ParsedOrder]:
        """Parse orders response.

        Args:
            response: Raw API response with orders data

        Returns:
            List of ParsedOrder objects
        """
        orders = []
        items = response.get("data", {}).get("items", [])

        for item in items:
            try:
                # Parse timestamps
                created_at = datetime.fromisoformat(
                    item["created-at"].replace("Z", "+00:00")
                )
                updated_at = datetime.fromisoformat(
                    item["updated-at"].replace("Z", "+00:00")
                )

                orders.append(ParsedOrder(
                    order_id=item["id"],
                    account_number=item.get("account-number", ""),
                    symbol=item.get("underlying-symbol", item.get("symbol", "")),
                    quantity=int(item.get("quantity", 0)),
                    order_type=item.get("order-type", ""),
                    side=item.get("side", ""),
                    status=item.get("status", ""),
                    price=float(item["price"]) if "price" in item else None,
                    time_in_force=item.get("time-in-force", ""),
                    created_at=created_at,
                    updated_at=updated_at
                ))
            except (KeyError, ValueError) as e:
                logger.error(f"Error parsing order: {e}")
                continue

        logger.info(f"Parsed {len(orders)} orders")
        return orders

    @staticmethod
    def parse_quotes(response: Dict[str, Any]) -> List[ParsedQuote]:
        """Parse quotes response.

        Args:
            response: Raw API response with quotes data

        Returns:
            List of ParsedQuote objects
        """
        quotes = []
        items = response.get("data", {}).get("items", [])

        for item in items:
            try:
                quotes.append(ParsedQuote(
                    symbol=item["symbol"],
                    bid_price=float(item.get("bid-price", 0)),
                    ask_price=float(item.get("ask-price", 0)),
                    last_price=float(item.get("last-price", 0)),
                    bid_size=int(item.get("bid-size", 0)),
                    ask_size=int(item.get("ask-size", 0)),
                    volume=int(item.get("volume", 0)),
                    open_price=float(item.get("open-price", 0)),
                    high_price=float(item.get("high-price", 0)),
                    low_price=float(item.get("low-price", 0)),
                    close_price=float(item.get("close-price", 0)),
                    change=float(item.get("change", 0)),
                    change_percent=float(item.get("change-percent", 0))
                ))
            except (KeyError, ValueError) as e:
                logger.error(f"Error parsing quote: {e}")
                continue

        logger.info(f"Parsed {len(quotes)} quotes")
        return quotes

    @staticmethod
    def parse_error(response: Dict[str, Any]) -> str:
        """Parse error response.

        Args:
            response: Raw API error response

        Returns:
            Human-readable error message
        """
        error = response.get("error", {})
        message = error.get("message", "Unknown error")
        code = error.get("code", "")
        details = error.get("errors", [])

        if details:
            detail_messages = [d.get("message", "") for d in details]
            message += " - " + "; ".join(detail_messages)

        if code:
            message = f"{code}: {message}"

        return message