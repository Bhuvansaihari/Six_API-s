"""
Caching module for Requirement Details API.

This module provides caching functionality using aiocache for
storing requirement details with TTL support.
"""

from aiocache import Cache
from aiocache.serializers import JsonSerializer
from typing import Optional
import logging

# Configure logging
logger = logging.getLogger(__name__)


# Global cache instance (will be initialized in main.py)
_cache: Optional[Cache] = None


def get_cache() -> Cache:
    """
    Get the global cache instance.
    
    Returns:
        Cache: The global cache instance
        
    Raises:
        RuntimeError: If cache is not initialized
    """
    global _cache
    if _cache is None:
        raise RuntimeError("Cache not initialized. Call initialize_cache() first.")
    return _cache


def initialize_cache() -> Cache:
    """
    Initialize the global cache instance.
    
    Returns:
        Cache: The initialized cache instance
    """
    global _cache
    if _cache is None:
        _cache = Cache(
            Cache.MEMORY,
            serializer=JsonSerializer(),
            namespace="requirement_details",
            timeout=300  # 5 minutes default TTL
        )
        logger.info("Cache initialized for Requirement Details API")
    return _cache


async def get_cached_requirement(requirement_id: int) -> Optional[dict]:
    """
    Get cached requirement details.
    
    Args:
        requirement_id (int): The requirement ID to look up
        
    Returns:
        Optional[dict]: Cached requirement data if found, None otherwise
    """
    try:
        cache = get_cache()
        key = f"req_{requirement_id}"
        cached_data = await cache.get(key)
        if cached_data:
            logger.debug(f"Cache hit for requirement_id={requirement_id}")
        else:
            logger.debug(f"Cache miss for requirement_id={requirement_id}")
        return cached_data
    except Exception as e:
        logger.warning(f"Error getting cached requirement: {e}")
        return None


async def set_cached_requirement(requirement_id: int, data: dict, ttl: int = 300):
    """
    Cache requirement details.
    
    Args:
        requirement_id (int): The requirement ID
        data (dict): The requirement data to cache
        ttl (int): Time-to-live in seconds (default: 300 = 5 minutes)
    """
    try:
        cache = get_cache()
        key = f"req_{requirement_id}"
        await cache.set(key, data, ttl=ttl)
        logger.debug(f"Cached requirement_id={requirement_id} with TTL={ttl}s")
    except Exception as e:
        logger.warning(f"Error caching requirement: {e}")
        # Fail silently if caching fails


async def clear_cache(requirement_id: Optional[int] = None):
    """
    Clear cache for a specific requirement or all cache.
    
    Args:
        requirement_id (Optional[int]): If provided, clear only this requirement's cache.
                                       If None, clear all cache.
    """
    try:
        cache = get_cache()
        if requirement_id:
            key = f"req_{requirement_id}"
            await cache.delete(key)
            logger.info(f"Cleared cache for requirement_id={requirement_id}")
        else:
            await cache.clear()
            logger.info("Cleared all Requirement Details API cache")
    except Exception as e:
        logger.warning(f"Error clearing cache: {e}")

