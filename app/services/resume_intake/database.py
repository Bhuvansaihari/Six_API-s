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
        
        Args:
            candidate_id: Candidate ID (cand_id) - required
            resume_json: Structured JSON data
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
        
        # Extract personal information - handle if it's a string (JSON) or dict
        personal_info_raw = resume_json.get('personal_information', {})
        if isinstance(personal_info_raw, str):
            try:
                personal_info = json.loads(personal_info_raw)
            except:
                personal_info = {}
        else:
            personal_info = personal_info_raw if isinstance(personal_info_raw, dict) else {}
        
        professional_exp_raw = resume_json.get('professional_experience', {})
        if isinstance(professional_exp_raw, str):
            try:
                professional_exp = json.loads(professional_exp_raw)
            except:
                professional_exp = {}
        else:
            professional_exp = professional_exp_raw if isinstance(professional_exp_raw, dict) else {}
        
        # Prepare update data for auto_apply_cand table
        update_data = {}
        
        # Name fields (only update if provided)
        if isinstance(personal_info, dict):
            name = personal_info.get('Name', '')
            name = str(name).strip() if name else ''
            if name:
                name_parts = name.split(' ', 1) if name else ['', '']
                update_data['first_name'] = name_parts[0] if name_parts[0] else None
                update_data['last_name'] = name_parts[1] if len(name_parts) > 1 and name_parts[1] else None
            
            # Email (only update if provided)
            email = personal_info.get('Email', '')
            email = str(email).strip() if email else ''
            if email:
                update_data['email'] = email
        
            # Phone numbers (only update if provided)
            phone = personal_info.get('Phone Number', '')
            phone = str(phone).strip() if phone else ''
            if phone:
                update_data['mobile'] = phone
            
            # Location fields
            location_raw = personal_info.get('Location', {})
            if isinstance(location_raw, str):
                try:
                    location = json.loads(location_raw)
                except:
                    location = {}
            else:
                location = location_raw if isinstance(location_raw, dict) else {}
            
            if isinstance(location, dict):
                update_data['city'] = location.get('city', '') or None
                update_data['country'] = location.get('Country', '') or None
                update_data['zipcode'] = location.get('Zipcode', '') or None
                # Combine address fields if available
                address_parts = []
                if location.get('address'):
                    address_parts.append(str(location.get('address')))
                if location.get('city'):
                    address_parts.append(str(location.get('city')))
                if location.get('State'):
                    address_parts.append(str(location.get('State')))
                if location.get('Zipcode'):
                    address_parts.append(str(location.get('Zipcode')))
                update_data['address'] = ", ".join(address_parts) if address_parts else None
        
        # Experience (from professional experience)
        if isinstance(professional_exp, dict):
            experience_years = professional_exp.get('Overall Experience', 0)
        else:
            experience_years = 0
        
        if isinstance(experience_years, str):
            # Try to extract number from string like "5 years"
            try:
                experience_years = float(''.join(filter(str.isdigit, experience_years.split()[0])))
            except:
                experience_years = 0
        update_data['experience'] = int(experience_years) if experience_years else 0
        
        # File information
        if os.path.exists(resume_file_path):
            try:
                file_size = os.path.getsize(resume_file_path)
                update_data['resume_file_size'] = file_size
                update_data['resume_file_name'] = os.path.basename(resume_file_path)
                file_extension = os.path.splitext(resume_file_path)[1].lower().replace('.', '')
                update_data['resume_file_type'] = file_extension
                update_data['resume_storage_path'] = resume_file_path
                update_data['resume_upload_date'] = datetime.utcnow().isoformat()
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
            if 'email' not in insert_data or not insert_data['email']:
                # Generate a temporary email if not provided
                insert_data['email'] = f"temp_{secrets.token_hex(8)}@example.com"
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
        
        Args:
            candidate_id: Candidate ID (cand_id) from auto_apply_cand table
            resume_data: Complete parsed resume JSON
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
        
        # Extract data from resume_data - handle if values are strings (JSON) or dicts
        def safe_get_dict(data, key, default=None):
            """Safely get a dict value, handling JSON strings."""
            value = data.get(key, default) if isinstance(data, dict) else default
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except:
                    return default if default is not None else {}
            return value if isinstance(value, dict) else (default if default is not None else {})
        
        def safe_get_list(data, key, default=None):
            """Safely get a list value, handling JSON strings."""
            value = data.get(key, default) if isinstance(data, dict) else default
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except:
                    return default if default is not None else []
            return value if isinstance(value, list) else (default if default is not None else [])
        
        personal_info = safe_get_dict(resume_data, 'personal_information', {})
        professional_exp = safe_get_dict(resume_data, 'professional_experience', {})
        skills_data = safe_get_dict(resume_data, 'skills', {})
        education_data = safe_get_list(resume_data, 'education', [])
        certification_data = safe_get_list(resume_data, 'certification', [])
        projects_data = safe_get_list(resume_data, 'projects', [])
        additional_info = safe_get_dict(resume_data, 'additional_information', {})
        
        # Prepare update data for parsed_cand_resume table
        update_data = {}
        
        # Always update resume_text and resume_json
        if resume_text:
            update_data['resume_text'] = resume_text
        update_data['resume_json'] = resume_data
        update_data['last_updated'] = datetime.utcnow().isoformat()
        
        # Personal information fields (only update if provided)
        if isinstance(personal_info, dict):
            name = personal_info.get('Name', '')
            name = str(name).strip() if name else ''
            if name:
                update_data['full_name'] = name
            
            email = personal_info.get('Email', '')
            email = str(email).strip() if email else ''
            if email:
                update_data['email'] = email
            
            phone = personal_info.get('Phone Number', '')
            phone = str(phone).strip() if phone else ''
            if phone:
                update_data['phone'] = phone
        
            # Location
            location_raw = personal_info.get('Location', {})
            if isinstance(location_raw, str):
                try:
                    location = json.loads(location_raw)
                except:
                    location = {}
            else:
                location = location_raw if isinstance(location_raw, dict) else {}
            
            if isinstance(location, dict):
                location_parts = []
                if location.get('city'):
                    location_parts.append(str(location.get('city')))
                if location.get('State'):
                    location_parts.append(str(location.get('State')))
                if location.get('Country'):
                    location_parts.append(str(location.get('Country')))
                update_data['location'] = ", ".join(location_parts) if location_parts else None
                update_data['zipcode'] = location.get('Zipcode', '') or None
            
            # Professional summary
            summary = personal_info.get('Summary', '')
            summary = str(summary).strip() if summary else ''
            if summary:
                update_data['professional_summary'] = summary
        
        # Experience
        if isinstance(professional_exp, dict):
            experience_years = professional_exp.get('Overall Experience', 0)
        else:
            experience_years = 0
        
        if isinstance(experience_years, str):
            try:
                experience_years = int(float(experience_years))
            except ValueError:
                experience_years = 0
        update_data['total_experience_years'] = experience_years
        
        # Skills - convert to arrays
        technical_skills = []
        if isinstance(skills_data, dict):
            tech_skills_str = skills_data.get('Technical Skills', '')
            if tech_skills_str:
                tech_skills_str = str(tech_skills_str)
                # Split by common delimiters and clean up
                technical_skills = [s.strip() for s in tech_skills_str.replace(',', '|').replace(';', '|').split('|') if s.strip()]
        
        soft_skills = []
        if isinstance(skills_data, dict):
            soft_skills_str = skills_data.get('Soft Skills', '')
            if soft_skills_str:
                soft_skills_str = str(soft_skills_str)
                soft_skills = [s.strip() for s in soft_skills_str.replace(',', '|').replace(';', '|').split('|') if s.strip()]
        
        languages = []
        if isinstance(skills_data, dict):
            languages_str = skills_data.get('Languages', '')
            if languages_str:
                languages_str = str(languages_str)
                languages = [s.strip() for s in languages_str.replace(',', '|').replace(';', '|').split('|') if s.strip()]
        
        update_data['technical_skills'] = technical_skills if technical_skills else None
        update_data['soft_skills'] = soft_skills if soft_skills else None
        update_data['languages'] = languages if languages else None
        
        # JSONB fields
        if isinstance(certification_data, list):
            update_data['certifications'] = certification_data
        if isinstance(education_data, list):
            update_data['education'] = education_data
        if isinstance(professional_exp, dict) and isinstance(professional_exp.get('experiences', []), list):
            update_data['work_experience'] = professional_exp.get('experiences', [])
        if isinstance(projects_data, list):
            update_data['projects'] = projects_data
        
        # Achievements
        achievements = []
        if isinstance(additional_info, dict):
            achievements_raw = additional_info.get('Achievements', '')
            if achievements_raw:
                if isinstance(achievements_raw, str):
                    achievements = [s.strip() for s in achievements_raw.replace(';', ',').split(',') if s.strip()]
                elif isinstance(achievements_raw, list):
                    achievements = [str(a).strip() for a in achievements_raw if str(a).strip()]
        update_data['achievements'] = achievements if achievements else None
        
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

