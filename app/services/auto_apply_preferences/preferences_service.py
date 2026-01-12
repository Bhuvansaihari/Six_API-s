"""
Preferences Service

Handles all interactions with auto_apply_agent_preferences table
and daily application limit logic.
"""

import logging
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone
from app.supabase.client import SupabaseClient
from app.constants import DEFAULT_DAILY_LIMIT
from .cache import get_cached_preferences, set_cached_preferences

logger = logging.getLogger(__name__)


async def get_candidate_preferences(cand_id: int) -> Dict:
    """
    Get preferences for a candidate, create default if not exists.
    
    Uses caching to reduce database load (5-minute TTL).
    
    Args:
        cand_id: Candidate ID
        
    Returns:
        Dict containing preference fields
    """
    # Check cache first
    cached = await get_cached_preferences(cand_id)
    if cached:
        logger.debug(f"Retrieved cached preferences for cand_id={cand_id}")
        return cached
    
    # Query database
    supabase = SupabaseClient()
    preferences = supabase.get_candidate_preferences(cand_id)
    
    if not preferences:
        # Create default preferences
        logger.info(f"No preferences found for cand_id={cand_id}, creating defaults")
        preferences = create_default_preferences(cand_id)
    
    # Cache the result
    await set_cached_preferences(cand_id, preferences)
    
    return preferences


async def check_daily_limit_reached(cand_id: int, limit: int) -> Tuple[bool, int]:
    """
    Check if candidate has reached their daily application limit.
    
    Always queries database for accurate count (no caching for limit enforcement).
    
    Args:
        cand_id: Candidate ID
        limit: Daily application limit
        
    Returns:
        Tuple of (limit_reached: bool, applications_today: int)
    """
    applications_today = await get_todays_application_count(cand_id)
    limit_reached = applications_today >= limit
    
    logger.info(
        f"Daily limit check for cand_id={cand_id}: "
        f"{applications_today}/{limit} applications today, "
        f"limit_reached={limit_reached}"
    )
    
    return (limit_reached, applications_today)


async def get_todays_application_count(cand_id: int) -> int:
    """
    Count applications made today from job_application_tracking.
    
    Uses UTC timezone for consistency.
    
    Args:
        cand_id: Candidate ID
        
    Returns:
        Number of applications made today
    """
    supabase = SupabaseClient()
    count = supabase.get_todays_application_count(cand_id)
    
    logger.debug(f"Applications today for cand_id={cand_id}: {count}")
    
    return count


def create_default_preferences(cand_id: int) -> Dict:
    """
    Create default preferences for a candidate.
    
    Default values:
    - daily_application_limit: 10
    - apply_most_recent_jobs_first: True
    - is_active: True
    
    Args:
        cand_id: Candidate ID
        
    Returns:
        Created preferences record
    """
    supabase = SupabaseClient()
    preferences = supabase.create_default_preferences(cand_id)
    
    logger.info(
        f"Created default preferences for cand_id={cand_id}: "
        f"limit={preferences.get('daily_application_limit', DEFAULT_DAILY_LIMIT)}, "
        f"is_active={preferences.get('is_active', True)}"
    )
    
    return preferences


async def check_existing_application(cand_id: int, requirement_id: str) -> Optional[Dict]:
    """
    Check if an application already exists for this candidate and job.
    
    Args:
        cand_id: Candidate ID
        requirement_id: Requirement ID
        
    Returns:
        Existing application record or None
    """
    supabase = SupabaseClient()
    existing = supabase.check_existing_application(cand_id, requirement_id)
    
    if existing:
        logger.info(
            f"Existing application found: cand_id={cand_id}, "
            f"requirement_id={requirement_id}, "
            f"application_id={existing.get('application_id')}"
        )
    
    return existing
