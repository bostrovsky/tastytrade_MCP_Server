"""WebSocket quote streaming service for real-time market data."""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Callable, Any
import websockets
from websockets.client import WebSocketClientProtocol
from datetime import datetime

logger = logging.getLogger(__name__)


class WebSocketQuoteService:
    """Service for streaming real-time quotes via WebSocket."""

    def __init__(self, ws_token: str, ws_url: str = "wss://tasty-openapi-ws.dxfeed.com/realtime"):
        """Initialize the WebSocket quote service.

        Args:
            ws_token: Authentication token for WebSocket
            ws_url: WebSocket URL (default: TastyTrade DXFeed)
        """
        self.ws_token = ws_token
        self.ws_url = ws_url
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.is_connected = False
        self.is_authenticated = False
        self.channel_counter = 0
        self.active_subscriptions: Dict[str, List[str]] = {}
        self.quote_callbacks: Dict[str, Callable] = {}
        self.last_quotes: Dict[str, Dict[str, Any]] = {}
        self._listener_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        """Establish WebSocket connection and authenticate.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info(f"Connecting to WebSocket: {self.ws_url}")
            self.websocket = await websockets.connect(self.ws_url)
            self.is_connected = True

            # Authenticate
            if await self._authenticate():
                self.is_authenticated = True
                logger.info("WebSocket connected and authenticated")
                return True
            else:
                await self.disconnect()
                return False

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            return False

    async def _authenticate(self) -> bool:
        """Authenticate with the WebSocket server.

        Returns:
            True if authentication successful
        """
        if not self.websocket:
            return False

        try:
            # Send SETUP first (required by DXLink protocol)
            setup_msg = {
                "type": "SETUP",
                "channel": 0,
                "version": "0.1-DXF-JS/0.3.0",
                "keepaliveTimeout": 60,
                "acceptKeepaliveTimeout": 60
            }
            await self.websocket.send(json.dumps(setup_msg))

            # Wait for SETUP response
            response = await asyncio.wait_for(self.websocket.recv(), timeout=5)
            setup_data = json.loads(response)

            if setup_data.get('type') != 'SETUP':
                logger.error(f"Unexpected setup response: {setup_data}")
                return False

            # CRITICAL: Wait for AUTH_STATE (UNAUTHORIZED) before sending AUTH
            logger.debug("Waiting for initial AUTH_STATE...")
            response = await asyncio.wait_for(self.websocket.recv(), timeout=5)
            auth_state_data = json.loads(response)

            if auth_state_data.get('type') != 'AUTH_STATE' or auth_state_data.get('state') != 'UNAUTHORIZED':
                logger.error(f"Expected AUTH_STATE UNAUTHORIZED, got: {auth_state_data}")
                return False

            logger.debug("Received AUTH_STATE UNAUTHORIZED, sending AUTH...")

            # Now send AUTH
            auth_msg = {
                "type": "AUTH",
                "channel": 0,
                "token": self.ws_token
            }
            await self.websocket.send(json.dumps(auth_msg))

            # Wait for AUTH response
            response = await asyncio.wait_for(self.websocket.recv(), timeout=5)
            auth_data = json.loads(response)

            if auth_data.get('type') == 'AUTH_STATE':
                if auth_data.get('state') == 'AUTHORIZED':
                    logger.info("WebSocket authentication successful")
                    return True
                else:
                    logger.error(f"Authentication failed: {auth_data}")
                    return False

            return False

        except asyncio.TimeoutError:
            logger.error("Authentication timeout")
            return False
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    async def subscribe_quotes(self, symbols: List[str], callback: Optional[Callable] = None) -> bool:
        """Subscribe to real-time quotes for symbols.

        Args:
            symbols: List of symbols to subscribe to
            callback: Optional callback function for quote updates

        Returns:
            True if subscription successful
        """
        if not self.is_authenticated or not self.websocket:
            logger.error("Not connected/authenticated")
            return False

        try:
            # Get a new channel
            self.channel_counter += 1
            channel = self.channel_counter

            # Request channel for FEED service
            channel_request = {
                "type": "CHANNEL_REQUEST",
                "channel": channel,
                "service": "FEED",
                "parameters": {"contract": "AUTO"}
            }
            await self.websocket.send(json.dumps(channel_request))

            # Wait for channel response
            response = await asyncio.wait_for(self.websocket.recv(), timeout=5)
            channel_data = json.loads(response)

            if channel_data.get('type') != 'CHANNEL_OPENED':
                logger.error(f"Failed to open channel: {channel_data}")
                return False

            # Setup feed
            feed_setup = {
                "type": "FEED_SETUP",
                "channel": channel,
                "acceptAggregation": False,
                "acceptDataFormat": "FULL",
                "acceptEventFields": {
                    "Quote": ["eventSymbol", "eventTime", "bidPrice", "askPrice",
                             "bidSize", "askSize", "bidTime", "askTime"]
                }
            }
            await self.websocket.send(json.dumps(feed_setup))

            # Subscribe to symbols
            subscription = {
                "type": "FEED_SUBSCRIPTION",
                "channel": channel,
                "add": [{"type": "Quote", "symbol": symbol} for symbol in symbols]
            }
            await self.websocket.send(json.dumps(subscription))

            # Store subscription info
            self.active_subscriptions[channel] = symbols
            if callback:
                for symbol in symbols:
                    self.quote_callbacks[symbol] = callback

            logger.info(f"Subscribed to {len(symbols)} symbols on channel {channel}")

            # Start listening for data if not already running
            if self._listener_task is None or self._listener_task.done():
                self._listener_task = asyncio.create_task(self._listen_for_quotes())
                logger.debug("Started quote listener task")

            return True

        except Exception as e:
            logger.error(f"Subscription failed: {e}")
            return False

    async def _listen_for_quotes(self):
        """Listen for incoming quote data."""
        if not self.websocket:
            return

        try:
            while self.is_connected:
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=60)
                    data = json.loads(message)

                    if data.get('type') == 'FEED_DATA':
                        await self._process_feed_data(data)
                    elif data.get('type') == 'KEEPALIVE':
                        # Send keepalive response
                        await self.websocket.send(json.dumps({
                            "type": "KEEPALIVE",
                            "channel": data.get('channel', 0)
                        }))

                except asyncio.TimeoutError:
                    # No data for 60 seconds, send keepalive
                    await self.websocket.send(json.dumps({
                        "type": "KEEPALIVE",
                        "channel": 0
                    }))
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("WebSocket connection closed")
                    self.is_connected = False
                    break

        except Exception as e:
            logger.error(f"Error in quote listener: {e}")
            self.is_connected = False

    async def _process_feed_data(self, data: Dict):
        """Process incoming feed data.

        Args:
            data: Feed data from WebSocket
        """
        channel = data.get('channel')
        for item in data.get('data', []):
            # Check if this is a quote data item (has eventSymbol and price fields)
            if 'eventSymbol' in item and 'bidPrice' in item:
                symbol = item.get('eventSymbol')
                if symbol:
                    quote = {
                        'symbol': symbol,
                        'bid': item.get('bidPrice', 0),
                        'ask': item.get('askPrice', 0),
                        'bidSize': item.get('bidSize', 0),
                        'askSize': item.get('askSize', 0),
                        'timestamp': datetime.now().isoformat()
                    }

                    # Store latest quote
                    self.last_quotes[symbol] = quote

                    # Call callback if registered
                    if symbol in self.quote_callbacks:
                        try:
                            await self.quote_callbacks[symbol](quote)
                        except Exception as e:
                            logger.error(f"Callback error for {symbol}: {e}")

    async def get_quote(self, symbol: str) -> Optional[Dict]:
        """Get the latest quote for a symbol.

        Args:
            symbol: Symbol to get quote for

        Returns:
            Latest quote data or None if not available
        """
        return self.last_quotes.get(symbol)

    async def disconnect(self):
        """Disconnect from WebSocket."""
        # Cancel listener task
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        if self.websocket:
            try:
                await self.websocket.close()
            except:
                pass
        self.is_connected = False
        self.is_authenticated = False
        logger.info("WebSocket disconnected")


class DXFeedSymbolConverter:
    """Convert TastyTrade symbols to DXFeed format."""

    @staticmethod
    def option_to_dxfeed(tastytrade_symbol: str) -> str:
        """Convert TastyTrade option symbol to DXFeed format.

        Args:
            tastytrade_symbol: e.g., "AAPL  251031P00225000"

        Returns:
            DXFeed format: e.g., ".AAPL251031P225"
        """
        parts = tastytrade_symbol.split()
        if len(parts) != 2:
            return tastytrade_symbol

        ticker = parts[0]
        option_part = parts[1]

        # Extract components
        date_part = option_part[:6]  # 251031
        put_call = option_part[6]    # P or C
        strike_part = option_part[7:]  # 00225000

        # Convert strike to number
        strike = float(strike_part) / 1000

        # Format for DXFeed
        if strike % 1 == 0:
            strike_str = str(int(strike))
        else:
            strike_str = str(strike).rstrip('0').rstrip('.')

        return f".{ticker}{date_part}{put_call}{strike_str}"

    @staticmethod
    def equity_to_dxfeed(symbol: str) -> str:
        """Convert equity symbol to DXFeed format.

        Args:
            symbol: e.g., "AAPL"

        Returns:
            DXFeed format: e.g., "AAPL"
        """
        # Equities don't need conversion
        return symbol.upper()