"""
Data Helper Utilities
"""
import json
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

def safe_get_dict(json_str: Any) -> Dict:
    """
    Safely parse a JSON string into a dictionary.
    Returns empty dict on failure.
    """
    if not json_str:
        return {}
    if isinstance(json_str, dict):
        return json_str
    try:
        val = json.loads(json_str)
        return val if isinstance(val, dict) else {}
    except (json.JSONDecodeError, TypeError):
        # Only log debug to avoid noise for expected empty/null values
        logger.debug(f"Failed to parse JSON dict: {json_str}")
        return {}

def safe_get_list(json_str: Any) -> List:
    """
    Safely parse a JSON string into a list.
    Returns empty list on failure.
    """
    if not json_str:
        return []
    if isinstance(json_str, list):
        return json_str
    try:
        val = json.loads(json_str)
        return val if isinstance(val, list) else []
    except (json.JSONDecodeError, TypeError):
        return []
