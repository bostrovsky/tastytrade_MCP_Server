"""Cache service with Redis and in-memory fallback."""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import redis.asyncio as redis
from redis.asyncio import ConnectionError, RedisError

from tastytrade_mcp.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class InMemoryCache:
    """Simple in-memory cache for development/testing."""
    
    def __init__(self):
        self._cache: dict[str, tuple[Any, Optional[datetime]]] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        async with self._lock:
            if key in self._cache:
                value, expires_at = self._cache[key]
                if expires_at and datetime.utcnow() > expires_at:
                    del self._cache[key]
                    return None
                return value
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL in seconds."""
        async with self._lock:
            expires_at = None
            if ttl:
                expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            self._cache[key] = (value, expires_at)
            return True
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        value = await self.get(key)
        return value is not None
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for a key."""
        async with self._lock:
            if key in self._cache:
                value, _ = self._cache[key]
                expires_at = datetime.utcnow() + timedelta(seconds=ttl)
                self._cache[key] = (value, expires_at)
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
    
    async def close(self) -> None:
        """Close cache (no-op for in-memory)."""
        pass


class CacheService:
    """Cache service with Redis and fallback to in-memory."""
    
    def __init__(self):
        self._redis_client: Optional[redis.Redis] = None
        self._in_memory: InMemoryCache = InMemoryCache()
        self._use_redis = settings.use_redis
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize cache service."""
        if self._initialized:
            return
        
        if self._use_redis:
            try:
                self._redis_client = await redis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=10,
                )
                # Test connection
                await self._redis_client.ping()
                logger.info("Redis cache connected successfully")
            except (ConnectionError, RedisError) as e:
                logger.warning(f"Redis not available, using in-memory cache: {e}")
                self._use_redis = False
                self._redis_client = None
        else:
            logger.info("Using in-memory cache (Redis disabled)")
        
        self._initialized = True
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        if not self._initialized:
            await self.initialize()
        
        try:
            if self._redis_client:
                value = await self._redis_client.get(key)
                return value
            else:
                return await self._in_memory.get(key)
        except RedisError as e:
            logger.error(f"Redis error on get: {e}")
            # Fallback to in-memory
            return await self._in_memory.get(key)
    
    async def set(
        self, 
        key: str, 
        value: str, 
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache with optional TTL in seconds."""
        if not self._initialized:
            await self.initialize()
        
        try:
            if self._redis_client:
                if ttl:
                    return await self._redis_client.setex(key, ttl, value)
                else:
                    return await self._redis_client.set(key, value)
            else:
                return await self._in_memory.set(key, value, ttl)
        except RedisError as e:
            logger.error(f"Redis error on set: {e}")
            # Fallback to in-memory
            return await self._in_memory.set(key, value, ttl)
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self._initialized:
            await self.initialize()
        
        try:
            if self._redis_client:
                result = await self._redis_client.delete(key)
                return result > 0
            else:
                return await self._in_memory.delete(key)
        except RedisError as e:
            logger.error(f"Redis error on delete: {e}")
            # Fallback to in-memory
            return await self._in_memory.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self._initialized:
            await self.initialize()
        
        try:
            if self._redis_client:
                return await self._redis_client.exists(key) > 0
            else:
                return await self._in_memory.exists(key)
        except RedisError as e:
            logger.error(f"Redis error on exists: {e}")
            # Fallback to in-memory
            return await self._in_memory.exists(key)
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration time for a key."""
        if not self._initialized:
            await self.initialize()
        
        try:
            if self._redis_client:
                return await self._redis_client.expire(key, ttl)
            else:
                return await self._in_memory.expire(key, ttl)
        except RedisError as e:
            logger.error(f"Redis error on expire: {e}")
            # Fallback to in-memory
            return await self._in_memory.expire(key, ttl)
    
    async def get_json(self, key: str) -> Optional[dict]:
        """Get JSON value from cache."""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON for key: {key}")
                return None
        return None
    
    async def set_json(
        self,
        key: str,
        value: dict,
        ttl: Optional[int] = None
    ) -> bool:
        """Set JSON value in cache."""
        try:
            json_str = json.dumps(value)
            return await self.set(key, json_str, ttl)
        except (TypeError, json.JSONEncodeError) as e:
            logger.error(f"Failed to encode JSON for key {key}: {e}")
            return False
    
    async def close(self) -> None:
        """Close cache connections."""
        if self._redis_client:
            await self._redis_client.close()
        await self._in_memory.close()
        self._initialized = False


# Global cache instance
_cache_service: Optional[CacheService] = None


async def get_cache() -> CacheService:
    """Get global cache service instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
        await _cache_service.initialize()
    return _cache_service