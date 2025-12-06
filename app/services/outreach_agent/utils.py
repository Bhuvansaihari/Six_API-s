"""
Utility functions for Outreach Agent V1.
"""
import re
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def extract_plain_description(raw_desc: str) -> str:
    """
    Extract plain text description from potentially JSON-encoded string.
    
    Accepts a job description string that may be:
      - Plain text
      - JSON string with a 'description' key (as produced by some parsers/storage)
    
    Args:
        raw_desc: Raw description string (may be JSON or plain text)
        
    Returns:
        str: Plain text description
    """
    try:
        jd_obj = json.loads(raw_desc)
        if isinstance(jd_obj, dict) and "description" in jd_obj:
            return jd_obj["description"]
    except Exception:
        pass
    return raw_desc


def format_single_requirement(requirement: Dict) -> str:
    """
    Format a requirement dictionary into a readable string.
    
    Args:
        requirement: Requirement dictionary with job details
        
    Returns:
        str: Formatted requirement string
    """
    description = extract_plain_description(requirement.get('requirement_description', 'N/A'))
    if len(description) > 300:
        description = description[:300] + '...'
    similarity_score = requirement.get('similarity_score', 0.0)
    match_percentage = f"{similarity_score * 100:.1f}%" if similarity_score else "N/A"
    min_pay = requirement.get('min_payrate')
    max_pay = requirement.get('max_payrate')
    if min_pay and max_pay:
        if min_pay == max_pay:
            pay_rate_str = f"${float(min_pay):.2f}/hr"
        else:
            pay_rate_str = f"${float(min_pay):.2f} - ${float(max_pay):.2f}/hr"
    elif min_pay:
        pay_rate_str = f"${float(min_pay):.2f}+/hr"
    elif max_pay:
        pay_rate_str = f"Up to ${float(max_pay):.2f}/hr"
    else:
        pay_rate_str = "Negotiable"
    duration = requirement.get('requirement_duration')
    duration_str = str(duration).strip() if duration else "Not specified"
    open_date = requirement.get('requirement_open_date')
    open_date_str = str(open_date) if open_date else "ASAP"
    location = requirement.get('location', 'Remote')
    formatted = f"""
    Job Requirement:
    - Title: {requirement.get('requirement_title', 'N/A')}
    - Client: {requirement.get('client_name', 'N/A')}
    - Location: {location}
    - Pay Rate: {pay_rate_str}
    - Duration: {duration_str}
    - Start Date: {open_date_str}
    - Match Score: {match_percentage}
    - Description: {description}
    """
    return formatted.strip()


def extract_first_name(full_name: str) -> str:
    """
    Extract first name from full name.
    
    Args:
        full_name: Full name string
        
    Returns:
        str: First name or "Candidate" if empty
    """
    if not full_name:
        return "Candidate"
    parts = full_name.strip().split()
    return parts[0] if parts else "Candidate"


def format_phone_number(phone: str, default_country_code: str = "+1") -> Optional[str]:
    """
    Format phone number to E.164 format.
    
    Args:
        phone: Phone number string (may contain formatting)
        default_country_code: Default country code if not present (default: "+1")
        
    Returns:
        str: Formatted phone number in E.164 format, or None if input is empty
    """
    if not phone:
        return None
    phone = re.sub(r'[^\d+]', '', phone)
    if phone.startswith('+'):
        return phone
    return f"{default_country_code}{phone}"


def validate_phone_number(phone: str) -> bool:
    """
    Validate phone number format (E.164).
    
    Args:
        phone: Phone number string to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not phone:
        return False
    pattern = r'^\+\d{10,15}$'
    return bool(re.match(pattern, phone))


def validate_webhook_payload(payload: dict) -> bool:
    """
    Validate webhook payload structure.
    
    Args:
        payload: Webhook payload dictionary
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = ['type', 'table', 'record']
    for field in required_fields:
        if field not in payload:
            logger.error(f"❌ Missing required field: {field}")
            return False
    record = payload.get('record', {})
    if 'cand_id' not in record:
        logger.error("❌ Missing cand_id in record")
        return False
    if 'requirement_id' not in record:
        logger.error("❌ Missing requirement_id in record")
        return False
    return True

