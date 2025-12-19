"""
Database connection and helper functions for Outreach Agent V1.

This module handles Supabase operations for fetching application details
and marking notifications as sent.
"""
import logging
from typing import Dict, Optional
from datetime import datetime

from supabase import create_client, Client
from config import get_settings

logger = logging.getLogger(__name__)

# Global Supabase client instance
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Get or create the Supabase client instance for Outreach Agent.
    
    Returns:
        Client: Supabase client instance
    """
    global _supabase_client
    if _supabase_client is None:
        settings = get_settings()

        # Use the unified Supabase service key configuration
        service_key = settings.supabase_service_key
        if not service_key and settings.supabase_service_role_key:
            service_key = settings.supabase_service_role_key
        if not service_key:
            raise ValueError("❌ SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_ROLE_KEY must be set in .env file")

        _supabase_client = create_client(
            settings.supabase_url,
            service_key.get_secret_value()
        )
        logger.info("Supabase client initialized for Outreach Agent")
    
    return _supabase_client


def get_application_details(cand_id: int, requirement_id: str) -> Optional[Dict]:
    """
    Get candidate details and requirement details for a specific application.
    
    Uses the Supabase RPC function 'get_application_details' to fetch
    all necessary information in a single call.
    
    Args:
        cand_id: The candidate's ID (from auto_apply_cand)
        requirement_id: The requirement ID (from parsed_requirements)
        
    Returns:
        Dictionary with candidate info, requirement info, and application details,
        or None if application not found or notifications already sent
    """
    try:
        logger.info(f"🔍 Querying database for cand_id: {cand_id}, requirement_id: {requirement_id}")
        
        supabase = get_supabase_client()
        
        # Call stored procedure using RPC
        response = supabase.rpc(
            'get_application_details',
            {
                'p_cand_id': cand_id,
                'p_requirement_id': requirement_id
            }
        ).execute()
        
        if not response.data or len(response.data) == 0:
            logger.info(f"⏳ Application not found or both notifications already sent")
            return None
        
        app = response.data[0]
        
        # Build full name
        full_name = f"{app['candidate_first_name']} {app['candidate_last_name']}".strip()
        
        # Extract candidate info
        candidate_info = {
            'cand_id': app['cand_id'],
            'candidate_name': full_name,
            'candidate_first_name': app['candidate_first_name'],
            'candidate_last_name': app['candidate_last_name'],
            'candidate_email': app['candidate_email'],
            'candidate_mobile': app.get('candidate_mobile'),
            'candidate_home': app.get('candidate_home'),
            'candidate_work': app.get('candidate_work'),
            'candidate_experience': app.get('candidate_experience', 0),
            'candidate_zipcode': app.get('candidate_zipcode'),
            'candidate_address': app.get('candidate_address'),
            'notify_email': app.get('notify_email', True),
            'notify_sms': app.get('notify_sms', False)
        }
        
        # Extract requirement details
        requirement_info = {
            'requirement_id': app['requirement_id'],
            'requirement_title': app['requirement_title'],
            'requirement_description': app.get('requirement_description', ''),
            'client_name': app.get('client_name', 'N/A'),
            'requirement_location': app.get('requirement_location', ''),
            'requirement_zipcode': app.get('requirement_zipcode', ''),
            'is_remote_location': app.get('is_remote_location', False),
            'min_payrate': app.get('min_payrate'),
            'max_payrate': app.get('max_payrate'),
            'requirement_duration': app.get('requirement_duration'),
            'requirement_open_date': app.get('requirement_open_date'),
            'matching_id': app.get('matching_id'),
            'similarity_score': float(app['similarity_score']) if app.get('similarity_score') else 0.0
        }
        
        application_id = app['application_id']
        application_status = app.get('application_status', 'MATCHED')
        applied_at = app.get('applied_at')
        email_sent = app.get('email_sent', False)
        sms_sent = app.get('sms_sent', False)
        
        # Build location string
        if requirement_info['is_remote_location']:
            location = 'Remote'
        else:
            location_parts = []
            if requirement_info['requirement_location']:
                location_parts.append(requirement_info['requirement_location'])
            if requirement_info['requirement_zipcode']:
                location_parts.append(requirement_info['requirement_zipcode'])
            location = ', '.join(location_parts) or 'Location TBD'
        
        requirement_info['location'] = location
        
        logger.info(f"✅ Found application: {requirement_info['requirement_title']} for {full_name}")
        logger.info(f"   Similarity Score: {requirement_info['similarity_score']:.4f}")
        logger.info(f"   Status: {application_status}")
        logger.info(f"   Email sent={email_sent}, SMS sent={sms_sent}")
        
        return {
            'candidate': candidate_info,
            'requirement': requirement_info,
            'application_id': application_id,
            'application_status': application_status,
            'applied_at': applied_at,
            'email_sent': email_sent,
            'sms_sent': sms_sent
        }
        
    except Exception as e:
        logger.error(f"❌ Error fetching application details: {str(e)}", exc_info=True)
        return None


def mark_email_sent(application_id: int) -> bool:
    """
    Mark an application as email sent in the database.
    
    Args:
        application_id: The application_id to update
        
    Returns:
        True if successful, False otherwise
    """
    try:
        supabase = get_supabase_client()
        
        response = supabase.table('job_application_tracking')\
            .update({
                'email_sent': True,
                'email_sent_at': datetime.now().isoformat()
            })\
            .eq('application_id', application_id)\
            .execute()
        
        logger.info(f"✅ Marked application_id {application_id} as email_sent=True")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error updating email_sent status: {str(e)}", exc_info=True)
        return False


def mark_sms_sent(application_id: int) -> bool:
    """
    Mark an application as SMS sent in the database.
    
    Args:
        application_id: The application_id to update
        
    Returns:
        True if successful, False otherwise
    """
    try:
        supabase = get_supabase_client()
        
        response = supabase.table('job_application_tracking')\
            .update({
                'sms_sent': True,
                'sms_sent_at': datetime.now().isoformat()
            })\
            .eq('application_id', application_id)\
            .execute()
        
        logger.info(f"✅ Marked application_id {application_id} as sms_sent=True")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error updating sms_sent status: {str(e)}", exc_info=True)
        return False

