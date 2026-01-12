"""
Auto Apply Preferences Service

This module handles candidate preferences for the auto-apply feature,
including daily application limits and preference management.
"""

from .preferences_service import (
    get_candidate_preferences,
    check_daily_limit_reached,
    get_todays_application_count,
    create_default_preferences,
    check_existing_application,
)

__all__ = [
    "get_candidate_preferences",
    "check_daily_limit_reached",
    "get_todays_application_count",
    "create_default_preferences",
    "check_existing_application",
]
