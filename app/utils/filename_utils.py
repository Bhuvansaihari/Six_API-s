"""
Filename Utilities

Provides functions for sanitizing and generating filenames.
"""

import re


def sanitize_filename(name: str) -> str:
    """
    Sanitize a string for use in filenames.
    
    - Removes special characters (accents, symbols)
    - Replaces spaces with underscores
    - Handles Unicode characters by stripping non-ascii/alphanumeric
    
    Args:
        name: Input string
        
    Returns:
        str: Sanitized safe filename string
    """
    if not name:
        return ""
        
    # Remove non-alphanumeric except spaces, hyphens, underscores
    sanitized = re.sub(r'[^\w\s-]', '', name)
    # Replace spaces with underscores
    sanitized = re.sub(r'\s+', '_', sanitized)
    # Remove leading/trailing underscores
    return sanitized.strip('_')


def generate_candidate_filename(first_name: str, last_name: str, candidate_id: int, extension: str) -> str:
    """
    Generate a filename from candidate information.
    
    Args:
        first_name: Candidate's first name
        last_name: Candidate's last name
        candidate_id: Candidate ID (fallback)
        extension: File extension (e.g., '.pdf')
        
    Returns:
        str: Generated filename
    """
    first = sanitize_filename(first_name) if first_name else ''
    last = sanitize_filename(last_name) if last_name else ''
    
    if first and last:
        name = f"{first}_{last}"
    elif first:
        name = first
    elif last:
        name = last
    else:
        name = f"candidate_{candidate_id}"
    
    # Ensure extension starts with dot
    if extension and not extension.startswith('.'):
        extension = f".{extension}"
        
    return f"{name}{extension}"
