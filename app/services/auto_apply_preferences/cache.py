"""
Caching layer for candidate preferences.

Uses in-memory cache with 5-minute TTL to reduce database load.
"""

import logging
from typing import Optional, Dict
from aiocache import Cache
from aiocache.serializers import JsonSerializer

logger = logging.getLogger(__name__)

# Initialize cache with 5-minute TTL
preferences_cache = Cache(
    Cache.MEMORY,
    serializer=JsonSerializer(),
    namespace="auto_apply_preferences",
    ttl=300  # 5 minutes
)


async def get_cached_preferences(cand_id: int) -> Optional[Dict]:
    """
    Get preferences from cache.
    
    Args:
        cand_id: Candidate ID
        
    Returns:
        Cached preferences or None if not found
    """
    try:
        cached = await preferences_cache.get(f"pref_{cand_id}")
        if cached:
            logger.debug(f"Cache hit for cand_id={cand_id}")
        return cached
    except Exception as e:
        logger.warning(f"Cache get failed for cand_id={cand_id}: {e}")
        return None


async def set_cached_preferences(cand_id: int, preferences: Dict) -> None:
    """
    Store preferences in cache.
    
    Args:
        cand_id: Candidate ID
        preferences: Preferences dictionary to cache
    """
    try:
        await preferences_cache.set(f"pref_{cand_id}", preferences)
        logger.debug(f"Cached preferences for cand_id={cand_id}")
    except Exception as e:
        logger.warning(f"Cache set failed for cand_id={cand_id}: {e}")


async def invalidate_cached_preferences(cand_id: int) -> None:
    """
    Invalidate cached preferences for a candidate.
    
    Use this when preferences are updated.
    
    Args:
        cand_id: Candidate ID
    """
    try:
        await preferences_cache.delete(f"pref_{cand_id}")
        logger.debug(f"Invalidated cache for cand_id={cand_id}")
    except Exception as e:
        logger.warning(f"Cache invalidation failed for cand_id={cand_id}: {e}")
