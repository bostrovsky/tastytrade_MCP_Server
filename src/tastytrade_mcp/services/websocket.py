"""WebSocket streaming service for real-time market data."""
import asyncio
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

import httpx
from tastytrade_mcp.config.settings import get_settings
from tastytrade_mcp.services.cache import get_cache
from tastytrade_mcp.services.tastytrade import TastyTradeService
from tastytrade_mcp.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class WebSocketManager:
    """Manages WebSocket connections and subscriptions for market data streaming."""

    def __init__(self):
        """Initialize WebSocket manager."""
        self.connections: Dict[str, Any] = {}  # connection_id -> connection info
        self.subscriptions: Dict[str, Set[str]] = defaultdict(set)  # symbol -> set of connection_ids
        self.user_subscriptions: Dict[str, Set[str]] = defaultdict(set)  # user_id -> set of symbols
        self.connection_status: str = "disconnected"
        self.last_heartbeat: Optional[datetime] = None
        self.message_count: int = 0
        self.start_time: datetime = datetime.utcnow()
        self.reconnect_attempts: int = 0
        self.max_reconnect_attempts: int = 10
        self.heartbeat_interval: int = 30  # seconds
        self.session_connections: Dict[str, str] = {}  # session_id -> connection_id
        self.latest_data: Dict[str, List[Dict]] = defaultdict(list)  # symbol -> list of recent data
        self.metrics: Dict[str, Any] = {
            "average_latency_ms": 0,
            "p95_latency_ms": 0,
            "p99_latency_ms": 0,
            "max_latency_ms": 0,
            "messages_per_second": 0,
            "bytes_per_second": 0,
            "dropped_messages": 0,
            "buffer_usage_percent": 0
        }
        self.latency_samples: List[float] = []
        self._lock = asyncio.Lock()
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._ws_connection = None

    async def subscribe(
        self,
        symbols: List[str],
        data_types: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Subscribe to market data streams for given symbols."""
        if data_types is None:
            data_types = ["quote", "trade"]

        # Check rate limits
        if len(symbols) > 100:
            raise ValueError("Cannot subscribe to more than 100 symbols at once")

        # Check user's total subscriptions
        if user_id:
            current_symbols = self.user_subscriptions.get(user_id, set())
            new_total = len(current_symbols) + len(symbols)
            if new_total > 100:
                raise ValueError(f"User rate limit exceeded: max 100 symbols per user (current: {len(current_symbols)}, requested: {len(symbols)})")

        # Get or create connection for session
        connection_id = None
        if session_id:
            connection_id = self.session_connections.get(session_id)

        if not connection_id:
            connection_id = f"ws_conn_{uuid4().hex[:8]}"
            if session_id:
                self.session_connections[session_id] = connection_id

        # Ensure connection is established
        if self.connection_status != "connected":
            await self._establish_connection()

        # Track subscriptions
        async with self._lock:
            for symbol in symbols:
                self.subscriptions[symbol].add(connection_id)
                if user_id:
                    self.user_subscriptions[user_id].add(symbol)

            # Store connection info
            self.connections[connection_id] = {
                "symbols": symbols,
                "data_types": data_types,
                "user_id": user_id,
                "session_id": session_id,
                "subscribed_at": datetime.utcnow()
            }

        # Send subscription request to WebSocket
        await self._send_subscription_request(symbols, data_types)

        return {
            "status": "subscribed",
            "symbols": symbols,
            "data_types": data_types,
            "connection_id": connection_id,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def unsubscribe(
        self,
        symbols: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Unsubscribe from market data streams."""
        connection_id = None
        if session_id:
            connection_id = self.session_connections.get(session_id)

        if not connection_id and not symbols:
            # Unsubscribe all for user
            if user_id:
                symbols = list(self.user_subscriptions.get(user_id, set()))
            else:
                symbols = ["ALL"]

        unsubscribed_symbols = []
        remaining_subscriptions = []

        async with self._lock:
            if symbols and symbols != ["ALL"]:
                # Unsubscribe specific symbols
                for symbol in symbols:
                    if connection_id and connection_id in self.subscriptions[symbol]:
                        self.subscriptions[symbol].discard(connection_id)
                        unsubscribed_symbols.append(symbol)
                    if user_id and symbol in self.user_subscriptions[user_id]:
                        self.user_subscriptions[user_id].discard(symbol)

                # Get remaining subscriptions
                if user_id:
                    remaining_subscriptions = list(self.user_subscriptions[user_id])
            else:
                # Unsubscribe all
                if connection_id:
                    conn_info = self.connections.get(connection_id, {})
                    unsubscribed_symbols = conn_info.get("symbols", [])
                    for symbol in unsubscribed_symbols:
                        self.subscriptions[symbol].discard(connection_id)
                    del self.connections[connection_id]

                if user_id:
                    unsubscribed_symbols = list(self.user_subscriptions[user_id])
                    self.user_subscriptions[user_id].clear()

        # Send unsubscribe request to WebSocket if needed
        if unsubscribed_symbols:
            await self._send_unsubscribe_request(unsubscribed_symbols)

        return {
            "status": "unsubscribed",
            "symbols": unsubscribed_symbols if unsubscribed_symbols else ["ALL"],
            "remaining_subscriptions": remaining_subscriptions
        }

    async def get_status(self) -> Dict[str, Any]:
        """Get current WebSocket connection status and subscriptions."""
        uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()

        # Build subscription list
        subscription_list = []
        for connection_id, conn_info in self.connections.items():
            for symbol in conn_info.get("symbols", []):
                subscription_list.append({
                    "symbol": symbol,
                    "data_types": conn_info.get("data_types", ["quote", "trade"])
                })

        # Check if we need to reconnect
        if self.connection_status == "disconnected":
            self.connection_status = "reconnecting"

        return {
            "connection_status": self.connection_status,
            "connection_id": list(self.connections.keys())[0] if self.connections else None,
            "subscriptions": subscription_list,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "heartbeat_interval": self.heartbeat_interval,
            "uptime_seconds": uptime_seconds,
            "message_count": self.message_count,
            "next_heartbeat_in": self._get_next_heartbeat_seconds()
        }

    async def get_latest_data(
        self,
        symbols: List[str],
        data_type: str = "latest"
    ) -> List[Dict[str, Any]]:
        """Get latest streaming data for symbols."""
        result = []
        for symbol in symbols:
            if symbol in self.latest_data:
                data = self.latest_data[symbol]
                if data:
                    result.append(data[-1])  # Get most recent
        return result

    async def get_metrics(self) -> Dict[str, Any]:
        """Get streaming performance metrics."""
        # Calculate latency percentiles
        if self.latency_samples:
            sorted_samples = sorted(self.latency_samples)
            n = len(sorted_samples)
            self.metrics["average_latency_ms"] = sum(sorted_samples) / n
            self.metrics["p95_latency_ms"] = sorted_samples[int(n * 0.95)]
            self.metrics["p99_latency_ms"] = sorted_samples[int(n * 0.99)]
            self.metrics["max_latency_ms"] = sorted_samples[-1]

        return self.metrics

    async def shutdown(self) -> Dict[str, Any]:
        """Gracefully shutdown all WebSocket connections."""
        # Cancel heartbeat task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        # Collect all symbols to unsubscribe
        all_symbols = set(self.subscriptions.keys())

        # Clear all subscriptions
        closed_connections = len(self.connections)
        self.connections.clear()
        self.subscriptions.clear()
        self.user_subscriptions.clear()
        self.session_connections.clear()
        self.connection_status = "disconnected"

        # Close WebSocket connection
        if self._ws_connection:
            await self._ws_connection.close()
            self._ws_connection = None

        return {
            "status": "shutdown",
            "unsubscribed_symbols": list(all_symbols),
            "closed_connections": closed_connections
        }

    async def reconnect(self) -> Dict[str, Any]:
        """Reconnect WebSocket with exponential backoff."""
        self.reconnect_attempts += 1

        # Calculate backoff delay
        delay = min(2 ** self.reconnect_attempts, 60)  # Max 60 seconds
        await asyncio.sleep(delay)

        # Try to reconnect
        try:
            await self._establish_connection()

            # Restore subscriptions
            restored_symbols = []
            for symbol, connection_ids in self.subscriptions.items():
                if connection_ids:
                    restored_symbols.append(symbol)

            if restored_symbols:
                await self._send_subscription_request(restored_symbols, ["quote", "trade"])

            self.reconnect_attempts = 0
            return {
                "status": "reconnected",
                "connection_id": f"ws_conn_new",
                "retry_count": self.reconnect_attempts,
                "restored_subscriptions": restored_symbols
            }
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            if self.reconnect_attempts < self.max_reconnect_attempts:
                # Schedule another reconnection attempt
                asyncio.create_task(self.reconnect())
            raise

    async def _establish_connection(self):
        """Establish WebSocket connection with OAuth authentication."""
        # In real implementation, would establish actual WebSocket connection
        # For now, simulate connection establishment
        self.connection_status = "connected"
        self.last_heartbeat = datetime.utcnow()

        # Start heartbeat monitoring
        if not self._heartbeat_task or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor())

    async def _send_subscription_request(self, symbols: List[str], data_types: List[str]):
        """Send subscription request to WebSocket."""
        # In real implementation, would send actual WebSocket message
        # For now, simulate subscription
        for symbol in symbols:
            # Generate mock data
            self.latest_data[symbol].append({
                "type": "quote",
                "symbol": symbol,
                "bid": 150.25,
                "ask": 150.27,
                "last": 150.26,
                "volume": 45678900,
                "timestamp": datetime.utcnow().isoformat()
            })
        self.message_count += len(symbols)

    async def _send_unsubscribe_request(self, symbols: List[str]):
        """Send unsubscribe request to WebSocket."""
        # In real implementation, would send actual WebSocket message
        # For now, simulate unsubscription
        for symbol in symbols:
            if symbol in self.latest_data:
                del self.latest_data[symbol]

    async def _heartbeat_monitor(self):
        """Monitor WebSocket connection with heartbeats."""
        while self.connection_status == "connected":
            try:
                await asyncio.sleep(self.heartbeat_interval)

                # Send heartbeat ping
                self.last_heartbeat = datetime.utcnow()

                # Check if we've received a pong
                if self.last_heartbeat:
                    time_since_heartbeat = (datetime.utcnow() - self.last_heartbeat).total_seconds()
                    if time_since_heartbeat > self.heartbeat_interval + 10:
                        # Connection seems dead, reconnect
                        logger.warning("Heartbeat timeout, reconnecting...")
                        self.connection_status = "disconnected"
                        await self.reconnect()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat monitor error: {e}")

    def _get_next_heartbeat_seconds(self) -> int:
        """Calculate seconds until next heartbeat."""
        if not self.last_heartbeat:
            return 0
        time_since = (datetime.utcnow() - self.last_heartbeat).total_seconds()
        next_in = max(0, self.heartbeat_interval - time_since)
        return int(next_in)

    def _record_latency(self, latency_ms: float):
        """Record latency sample for metrics."""
        self.latency_samples.append(latency_ms)
        # Keep only last 1000 samples
        if len(self.latency_samples) > 1000:
            self.latency_samples = self.latency_samples[-1000:]

    def _update_throughput_metrics(self, message_size: int):
        """Update throughput metrics."""
        # Calculate messages per second
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        if uptime > 0:
            self.metrics["messages_per_second"] = self.message_count / uptime

        # Update other metrics (simplified for now)
        self.metrics["bytes_per_second"] = message_size * self.metrics["messages_per_second"]
        self.metrics["buffer_usage_percent"] = min(45, len(self.latest_data) * 5)  # Simulated