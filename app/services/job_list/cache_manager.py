"""
Cache manager for Job List API responses.

This module provides caching with TTL (Time To Live) support for caching
job list results. Supports both in-memory and Redis caching.
"""

import time
import hashlib
import json
import logging
from typing import Any, Optional, Dict, Tuple
from config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

# Try to import Redis, fall back to None if not available
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available. Install redis package for distributed caching.")


class CacheManager:
    """
    In-memory cache manager with TTL support.
    """
    
    def __init__(self, default_ttl: int = 300):
        """
        Initialize the cache manager.
        """
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self.default_ttl = default_ttl
        logger.info(f"Job List Cache manager initialized with TTL: {default_ttl}s")
    
    def _generate_list_key(self, candidate_id: int) -> str:
        """Generate a cache key for job list."""
        return f"jobs:list:{candidate_id}"

    def get_list(self, candidate_id: int) -> Optional[Any]:
        """Retrieve list results from the cache if it exists and hasn't expired."""
        key = self._generate_list_key(candidate_id)
        
        if key not in self._cache:
            logger.debug(f"Cache miss for key: {key}")
            return None
        
        value, expiration_time = self._cache[key]
        
        if time.time() > expiration_time:
            del self._cache[key]
            logger.debug(f"Cache entry expired and removed: {key}")
            return None
        
        logger.debug(f"Cache hit for key: {key}")
        return value

    def set_list(
        self,
        candidate_id: int,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """Store list results in the cache with an expiration time."""
        key = self._generate_list_key(candidate_id)
        expiration_time = time.time() + (ttl or self.default_ttl)
        self._cache[key] = (value, expiration_time)
        logger.debug(f"Value cached with key: {key}, expires in {ttl or self.default_ttl}s")

    def clear(self) -> None:
        """Clear all entries from the cache."""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cache cleared. Removed {count} entries")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        current_time = time.time()
        active_entries = sum(
            1 for _, expiration_time in self._cache.values()
            if current_time <= expiration_time
        )
        expired_entries = len(self._cache) - active_entries
        
        return {
            "total_entries": len(self._cache),
            "active_entries": active_entries,
            "expired_entries": expired_entries,
            "default_ttl": self.default_ttl,
            "type": "memory"
        }


class RedisCacheManager:
    """
    Redis-based cache manager with TTL support.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: Optional[str] = None,
        db: int = 0,
        socket_timeout: int = 5,
        default_ttl: int = 300
    ):
        """Initialize the Redis cache manager."""
        if not REDIS_AVAILABLE:
            raise RuntimeError("Redis package not installed.")
        
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                password=password,
                db=db,
                socket_timeout=socket_timeout,
                decode_responses=True,
                socket_connect_timeout=socket_timeout
            )
            self.redis_client.ping()
            self.default_ttl = default_ttl
            logger.info(f"Job List Redis cache manager initialized. Host: {host}:{port}, TTL: {default_ttl}s")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise RuntimeError(f"Failed to connect to Redis: {e}") from e
    
    def _generate_list_key(self, candidate_id: int) -> str:
        """Generate a cache key for job list."""
        return f"jobs:list:{candidate_id}"

    def get_list(self, candidate_id: int) -> Optional[Any]:
        """Retrieve list results from Redis cache."""
        try:
            key = self._generate_list_key(candidate_id)
            cached_value = self.redis_client.get(key)
            
            if cached_value is None:
                logger.debug(f"Cache miss for key: {key}")
                return None
            
            logger.debug(f"Cache hit for key: {key}")
            return json.loads(cached_value)
        except redis.RedisError as e:
            logger.warning(f"Redis error during get operation: {e}")
            return None
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Error deserializing cached value: {e}")
            return None

    def set_list(
        self,
        candidate_id: int,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """Store list results in Redis cache with TTL."""
        try:
            key = self._generate_list_key(candidate_id)
            serialized_value = json.dumps(value)
            ttl_seconds = ttl or self.default_ttl
            
            self.redis_client.setex(key, ttl_seconds, serialized_value)
            logger.debug(f"Value cached in Redis with key: {key}, expires in {ttl_seconds}s")
        except redis.RedisError as e:
            logger.warning(f"Redis error during set operation: {e}")
        except (TypeError, ValueError) as e:
            logger.error(f"Error serializing value for cache: {e}")

    def clear(self) -> None:
        """Clear all cache entries (by pattern)."""
        try:
            keys = self.redis_client.keys("jobs:*")
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} entries from Redis cache")
            else:
                logger.info("No cache entries to clear")
        except redis.RedisError as e:
            logger.error(f"Redis error during clear operation: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics from Redis."""
        try:
            keys = self.redis_client.keys("jobs:*")
            info = self.redis_client.info("stats")
            
            return {
                "total_entries": len(keys),
                "active_entries": len(keys),
                "expired_entries": 0,
                "default_ttl": self.default_ttl,
                "redis_connected": True,
                "type": "redis"
            }
        except redis.RedisError as e:
            logger.error(f"Redis error getting stats: {e}")
            return {
                "redis_connected": False,
                "error": str(e)
            }


# Global cache instance
_cache_manager: Optional[Any] = None


def get_cache_manager():
    """
    Get or create the global cache manager instance.
    """
    global _cache_manager
    
    if _cache_manager is None:
        settings = get_settings()
        # Reusing recommendations settings for simplicity as requested
        # Ideally should have separate settings, but this is efficient reuse
        cache_type = getattr(settings, "recommendations_cache_type", "memory")
        cache_ttl = getattr(settings, "recommendations_cache_ttl", 300)
        
        if cache_type.lower() == "redis" and REDIS_AVAILABLE:
            try:
                redis_password = settings.recommendations_redis_password.get_secret_value() if settings.recommendations_redis_password else None
                _cache_manager = RedisCacheManager(
                    host=settings.recommendations_redis_host,
                    port=settings.recommendations_redis_port,
                    password=redis_password,
                    db=settings.recommendations_redis_db,
                    socket_timeout=settings.recommendations_redis_socket_timeout,
                    default_ttl=cache_ttl
                )
                logger.info("Using Redis cache manager for Job List")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis cache, falling back to memory cache: {e}")
                _cache_manager = CacheManager(default_ttl=cache_ttl)
                logger.info("Using in-memory cache manager (fallback)")
        else:
            _cache_manager = CacheManager(default_ttl=cache_ttl)
            logger.info("Using in-memory cache manager for Job List")
    
    return _cache_manager
