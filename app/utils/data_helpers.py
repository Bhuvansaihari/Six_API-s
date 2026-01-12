"""
Data Helper Utilities

Provides safe utility functions for data type conversion and extraction.
"""

import json
from typing import Any, Dict, List, Optional


def safe_get_dict(value: Any, default: Optional[Dict] = None) -> Dict:
    """
    Safely convert value to dict.
    
    Args:
        value: The value to convert (can be dict or JSON string)
        default: Default value if conversion fails (default: {})
        
    Returns:
        Dict: Converted dictionary or default
    """
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return default if default is not None else {}
    return value if isinstance(value, dict) else (default if default is not None else {})


def safe_get_list(value: Any, default: Optional[List] = None) -> List:
    """
    Safely convert value to list.
    
    Args:
        value: The value to convert (can be list or JSON string)
        default: Default value if conversion fails (default: [])
        
    Returns:
        List: Converted list or default
    """
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return default if default is not None else []
    return value if isinstance(value, list) else (default if default is not None else [])
