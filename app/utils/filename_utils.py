"""
Filename Utility Functions
"""
import re

def sanitize_filename(name: str) -> str:
    """Sanitize string to be safe for filenames"""
    if not name:
        return "candidate"
    
    # Replace unsafe characters (non-alphanumeric, non-dash, non-dot) with underscore
    clean = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', name)
    # Remove duplicate underscores
    clean = re.sub(r'_+', '_', clean)
    return clean.strip('_')

def generate_candidate_filename(first_name: str, last_name: str, extension: str = "pdf") -> str:
    """
    Generate standardized filename: FirstName_LastName.ext
    """
    first = sanitize_filename(first_name)
    last = sanitize_filename(last_name)
    
    # Ensure extension starts with dot
    if not extension.startswith('.'):
        extension = f".{extension}"
        
    if not first and not last:
        return f"candidate_resume{extension}"
    
    # Handle cases where one name is missing
    if not first:
        return f"{last}{extension}"
    if not last:
        return f"{first}{extension}"
        
    return f"{first}_{last}{extension}"
