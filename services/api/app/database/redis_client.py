"""Redis client connection and utility wrapper for caching GraphRAG queries."""

import os
import json
import logging
from typing import Optional, Any
import redis

logger = logging.getLogger(__name__)


class RedisClient:
    """Wrapper around Redis connection to cache GraphRAG queries."""

    def __init__(self):
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", "6379"))
        self._client: Optional[redis.Redis] = None
        self.enabled = False

    def connect(self):
        """Establish connection to Redis and ping the server."""
        try:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                decode_responses=True,
                socket_connect_timeout=2.0,
            )
            # Test connectivity
            self._client.ping()
            self.enabled = True
            logger.info("Connected to Redis cache at %s:%d", self.host, self.port)
        except redis.RedisError as e:
            self.enabled = False
            logger.warning(
                "Failed to connect to Redis at %s:%d: %s. Caching disabled.",
                self.host,
                self.port,
                e,
            )

    def get(self, key: str) -> Optional[Any]:
        """Retrieve and parse JSON value from cache."""
        if not self.enabled or not self._client:
            return None
        try:
            val = self._client.get(key)
            if val:
                return json.loads(val)
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.warning("Redis GET failed for key %s: %s", key, e)
        return None

    def set(self, key: str, value: Any, ex: int = 300):
        """Cache value as serialized JSON with default 5-min TTL (300s)."""
        if not self.enabled or not self._client:
            return
        try:
            self._client.set(key, json.dumps(value), ex=ex)
        except (redis.RedisError, TypeError) as e:
            logger.warning("Redis SET failed for key %s: %s", key, e)

    def clear_cache(self):
        """Evict all GraphRAG cached search queries on data updates."""
        if not self.enabled or not self._client:
            return
        try:
            keys = self._client.keys("graphrag:*")
            if keys:
                self._client.delete(*keys)
                logger.info("Cleared %d cached GraphRAG keys from Redis", len(keys))
        except redis.RedisError as e:
            logger.warning("Failed to clear Redis cache: %s", e)


redis_client = RedisClient()
