"""Database service for managing resume data in Supabase with connection pooling."""

import logging
import json
import secrets
import os
from typing import Optional, Dict, Any
from datetime import datetime
from supabase import create_client, Client

from config import get_settings

logger = logging.getLogger(__name__)


# Connection pool configuration
# Supabase client uses httpx under the hood which handles connection pooling automatically
# We use a singleton pattern to reuse connections
_client_instance: Optional[Client] = None


def get_database_client() -> Client:
    """
    Get or create a cached Supabase client with connection pooling.
    Uses singleton pattern to ensure connection reuse and pooling.
    
    Returns:
        Supabase client instance
        
    Raises:
        ValueError: If Supabase credentials are not configured
    """
    global _client_instance
    
    if _client_instance is not None:
        return _client_instance
    
    settings = get_settings()

    if not settings.supabase_url:
        raise ValueError("Supabase URL not configured. Please set SUPABASE_URL in .env file")

    # Use the same service key logic as the shared Supabase client:
    # prefer SUPABASE_SERVICE_KEY, fall back to SUPABASE_SERVICE_ROLE_KEY
    service_key = settings.supabase_service_key
    if not service_key and settings.supabase_service_role_key:
        service_key = settings.supabase_service_role_key
    if not service_key:
        raise ValueError("Supabase service key not configured. Please set SUPABASE_SERVICE_KEY in .env file")

    # Create client - httpx (used by Supabase) handles connection pooling automatically
    # Default pool limits: max_connections=100, max_keepalive_connections=20
    _client_instance = create_client(
        settings.supabase_url,
        service_key.get_secret_value()
    )
    
    return _client_instance


class DatabaseService:
    """Manages resume data in Supabase database with connection pooling."""
    
    def __init__(self):
        """Initialize Supabase client with connection pooling."""
        self.client = get_database_client()
        settings = get_settings()
        self.raw_resumes_table = settings.raw_resumes_table
        self.parsed_resumes_table = settings.parsed_resumes_table
    
    def update_raw_resume(self, candidate_id: int, resume_json: Dict[str, Any], resume_file_path: str) -> Dict[str, Any]:
        """
        Upsert raw resume data in auto_apply_cand table.
        Inserts if candidate doesn't exist, updates if candidate exists.
        
        Uses canonical schema: basic_information, location_information, skills_expertise
        
        Args:
            candidate_id: Candidate ID (cand_id) - required
            resume_json: Structured JSON data (canonical schema)
            resume_file_path: Path to the resume file
            
        Returns:
            Dictionary with success status and cand_id
            
        Raises:
            ValueError: If candidate_id is missing or client not initialized
            FileNotFoundError: If resume file doesn't exist
            Exception: If database operation fails
        """
        if not self.client:
            raise ValueError("Supabase client not initialized")
        
        if not candidate_id:
            raise ValueError("candidate_id is required")
        
        # Helper function to safely get dict value
        def safe_get_dict(value, default=None):
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except:
                    return default if default is not None else {}
            return value if isinstance(value, dict) else (default if default is not None else {})
        
        # Extract from canonical schema
        basic_info = safe_get_dict(resume_json.get('basic_information'), {})
        location_info = safe_get_dict(resume_json.get('location_information'), {})
        skills_info = safe_get_dict(resume_json.get('skills_expertise'), {})
        
        # Prepare update data for auto_apply_cand table
        update_data = {}
        
        # Name fields from basic_information
        if isinstance(basic_info, dict):
            first_name = basic_info.get('first_name', '')
            last_name = basic_info.get('last_name', '')
            first_name = str(first_name).strip() if first_name else ''
            last_name = str(last_name).strip() if last_name else ''
            if first_name:
                update_data['first_name'] = first_name
            if last_name:
                update_data['last_name'] = last_name
            
            # Note: Email is NOT updated from resume - it's already set by another service before resume upload
            
            # Phone - prefer mobile_phone, fallback to home_phone or work_phone
            mobile = basic_info.get('mobile_phone', '')
            if not mobile:
                mobile = basic_info.get('home_phone', '')
            if not mobile:
                mobile = basic_info.get('work_phone', '')
            mobile = str(mobile).strip() if mobile else ''
            if mobile:
                update_data['mobile'] = mobile
        
        # Location fields from location_information
        if isinstance(location_info, dict):
            city = location_info.get('city', '')
            city = str(city).strip() if city else ''
            if city:
                update_data['city'] = city
            
            country = location_info.get('country', '')
            country = str(country).strip() if country else ''
            if country:
                update_data['country'] = country
            
            zipcode = location_info.get('zipcode', '')
            zipcode = str(zipcode).strip() if zipcode else ''
            if zipcode:
                update_data['zipcode'] = zipcode
            
            # Combine address fields
            address_parts = []
            address = location_info.get('address', '')
            if address:
                address_parts.append(str(address))
            if city:
                address_parts.append(city)
            if country:
                address_parts.append(country)
            if zipcode:
                address_parts.append(zipcode)
            if address_parts:
                update_data['address'] = ", ".join(address_parts)
        
        # Experience from skills_expertise
        if isinstance(skills_info, dict):
            experience_years = skills_info.get('total_experience_years', 0)
            if experience_years is None:
                experience_years = 0
            try:
                experience_years = int(float(experience_years))
            except (ValueError, TypeError):
                experience_years = 0
            update_data['experience'] = experience_years
        
        # File information
        if os.path.exists(resume_file_path):
            try:
                # Generate candidate-based filename
                first_name = update_data.get('first_name', '').strip()
                last_name = update_data.get('last_name', '').strip()
                
                # Create filename from candidate name
                if first_name and last_name:
                    # Sanitize names for filename (remove special characters)
                    safe_first = ''.join(c for c in first_name if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
                    safe_last = ''.join(c for c in last_name if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
                    candidate_name = f"{safe_first}_{safe_last}"
                elif first_name:
                    safe_first = ''.join(c for c in first_name if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
                    candidate_name = safe_first
                elif last_name:
                    safe_last = ''.join(c for c in last_name if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
                    candidate_name = safe_last
                else:
                    # Fallback to candidate_id if no name available
                    candidate_name = f"candidate_{candidate_id}"
                
                # Get file extension from original file
                file_extension = os.path.splitext(resume_file_path)[1].lower()  # e.g., '.pdf'
                
                # Create new filename
                new_filename = f"{candidate_name}{file_extension}"
                
                # Store file metadata
                file_size = os.path.getsize(resume_file_path)
                update_data['resume_file_size'] = file_size
                update_data['resume_file_name'] = new_filename  # e.g., 'John_Doe.pdf'
                update_data['resume_file_type'] = file_extension.replace('.', '')  # e.g., 'pdf'
                update_data['resume_storage_path'] = resume_file_path  # Keep original path
                update_data['resume_upload_date'] = datetime.utcnow().isoformat()
                
                logger.info(f"Resume filename set to: {new_filename} for candidate_id={candidate_id}")
            except Exception as e:
                raise Exception(f"Failed to read file: {str(e)}")
        else:
            raise FileNotFoundError(f"File not found at {resume_file_path}")

        
        # Upsert auto_apply_cand table (insert if not exists, update if exists)
        try:
            # Prepare insert data with all required fields
            insert_data = update_data.copy()
            insert_data['cand_id'] = candidate_id
            
            # Required fields for insert
            if 'first_name' not in insert_data or not insert_data['first_name']:
                insert_data['first_name'] = 'Unknown'
            if 'last_name' not in insert_data or not insert_data['last_name']:
                insert_data['last_name'] = 'User'
            # Note: Email is NOT set here - it's already set by another service before resume upload
            if 'password' not in insert_data:
                # Generate a random password if not provided
                insert_data['password'] = secrets.token_urlsafe(16)
            
            # Default values for insert
            insert_data['over_18_age'] = True
            insert_data['relocation'] = False
            insert_data['notify_email'] = True
            insert_data['notify_sms'] = False
            
            # Try insert first - if it fails due to existing record, then update
            try:
                # Insert without select (Supabase insert may not support select in all versions)
                result = self.client.table(self.raw_resumes_table).insert(insert_data).execute()
                action = "inserted"
            except Exception as insert_error:
                error_str = str(insert_error).lower()
                # If insert fails due to unique constraint or existing record, try update
                if any(keyword in error_str for keyword in ["unique", "duplicate", "violates", "already exists", "constraint"]):
                    try:
                        update_result = self.client.table(self.raw_resumes_table).update(update_data).eq("cand_id", candidate_id).execute()
                        action = "updated"
                    except Exception as update_error:
                        raise Exception(f"Failed to update existing record: {str(update_error)}")
                else:
                    # Some other error occurred during insert
                    raise insert_error
            
            return {
                "success": True,
                "candidate_id": candidate_id,
                "message": f"Successfully {action} raw resume for Candidate ID: {candidate_id}"
            }
        except Exception as e:
            raise Exception(f"Failed to upsert {self.raw_resumes_table} for cand_id {candidate_id}: {str(e)}")
    
    def update_parsed_resume(self, candidate_id: int, resume_data: Dict[str, Any], resume_text: str = None) -> Dict[str, Any]:
        """
        Update parsed resume data in parsed_cand_resume table.
        
        Maps from canonical schema to database fields using normalize function.
        
        Args:
            candidate_id: Candidate ID (cand_id) from auto_apply_cand table
            resume_data: Complete parsed resume JSON (canonical schema)
            resume_text: Raw text content of the resume
            
        Returns:
            Dictionary with success status and cand_id
            
        Raises:
            ValueError: If candidate_id is missing or client not initialized
            Exception: If database operation fails
        """
        if not self.client:
            raise ValueError("Supabase client not initialized")
        
        if not candidate_id:
            raise ValueError("candidate_id is required")
        
        def normalize(value):
            """Normalize empty values to None."""
            if value in ("", [], {}):
                return None
            return value
        
        # Helper function to safely get dict value
        def safe_get_dict(value, default=None):
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except:
                    return default if default is not None else {}
            return value if isinstance(value, dict) else (default if default is not None else {})
        
        def safe_get_list(value, default=None):
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except:
                    return default if default is not None else []
            return value if isinstance(value, list) else (default if default is not None else [])
        
        # Extract from canonical schema
        basic = safe_get_dict(resume_data.get('basic_information'), {})
        location = safe_get_dict(resume_data.get('location_information'), {})
        skills = safe_get_dict(resume_data.get('skills_expertise'), {})
        education_data = safe_get_list(resume_data.get('education'), [])
        certifications_data = safe_get_list(resume_data.get('certifications'), [])
        work_experience_data = safe_get_list(resume_data.get('work_experience'), [])
        projects_data = safe_get_list(resume_data.get('projects'), [])
        achievements_data = safe_get_list(resume_data.get('achievements'), [])
        
        # Prepare update data for parsed_cand_resume table
        update_data = {}
        
        # Always update resume_text and resume_json
        if resume_text:
            update_data['resume_text'] = resume_text
        update_data['resume_json'] = resume_data
        update_data['last_updated'] = datetime.utcnow().isoformat()
        
        # Map from canonical schema to DB fields
        # Full name
        first_name = basic.get('first_name', '') or ''
        last_name = basic.get('last_name', '') or ''
        full_name = f"{first_name} {last_name}".strip()
        update_data['full_name'] = normalize(full_name)
        
        # Email
        email = basic.get('email', '') or ''
        update_data['email'] = normalize(email)
        
        # Phone - prefer mobile_phone
        phone = basic.get('mobile_phone', '') or basic.get('home_phone', '') or basic.get('work_phone', '') or ''
        update_data['phone'] = normalize(phone)
        
        # Location
        location_parts = []
        city = location.get('city', '') or ''
        country = location.get('country', '') or ''
        if city:
            location_parts.append(city)
        if country:
            location_parts.append(country)
        update_data['location'] = normalize(", ".join(location_parts) if location_parts else None)
        update_data['zipcode'] = normalize(location.get('zipcode', '') or '')
        
        # Professional summary
        professional_summary = resume_data.get('professional_summary', '') or ''
        update_data['professional_summary'] = normalize(professional_summary)
        
        # Total experience years
        total_exp = skills.get('total_experience_years', 0)
        if total_exp is None:
            total_exp = 0
        try:
            total_exp = int(float(total_exp))
        except (ValueError, TypeError):
            total_exp = 0
        update_data['total_experience_years'] = total_exp
        
        # Skills - already arrays in canonical schema
        technical_skills = skills.get('technical_skills', [])
        soft_skills = skills.get('soft_skills', [])
        languages = skills.get('languages', [])
        update_data['technical_skills'] = normalize(technical_skills) if technical_skills else None
        update_data['soft_skills'] = normalize(soft_skills) if soft_skills else None
        update_data['languages'] = normalize(languages) if languages else None
        
        # JSONB fields - store as-is from canonical schema
        update_data['education'] = normalize(education_data) if education_data else None
        update_data['certifications'] = normalize(certifications_data) if certifications_data else None
        update_data['work_experience'] = normalize(work_experience_data) if work_experience_data else None
        update_data['projects'] = normalize(projects_data) if projects_data else None
        update_data['achievements'] = normalize(achievements_data) if achievements_data else None
        
        # Use upsert (insert or update) based on cand_id
        try:
            # Try insert first - if it fails due to existing record, then update
            update_data['cand_id'] = candidate_id
            update_data['parsed_at'] = datetime.utcnow().isoformat()
            
            try:
                # Insert without select (Supabase insert may not support select in all versions)
                result = self.client.table(self.parsed_resumes_table).insert(update_data).execute()
                action = "inserted"
            except Exception as insert_error:
                error_str = str(insert_error).lower()
                # If insert fails due to unique constraint or existing record, try update
                if any(keyword in error_str for keyword in ["unique", "duplicate", "violates", "already exists", "constraint"]):
                    try:
                        # Remove cand_id and parsed_at from update_data for update (they shouldn't be updated)
                        update_data_for_update = {k: v for k, v in update_data.items() if k not in ['cand_id', 'parsed_at']}
                        result = self.client.table(self.parsed_resumes_table).update(update_data_for_update).eq("cand_id", candidate_id).execute()
                        action = "updated"
                    except Exception as update_error:
                        raise Exception(f"Failed to update existing record: {str(update_error)}")
                else:
                    # Some other error occurred during insert
                    raise insert_error
            
            return {
                "success": True,
                "candidate_id": candidate_id,
                "message": f"Successfully updated parsed resume data for Candidate ID: {candidate_id}"
            }
        except Exception as e:
            raise Exception(f"Failed to update {self.parsed_resumes_table} for cand_id {candidate_id}: {str(e)}")

