from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from datetime import date

from supabase import create_client, Client
from config import get_settings

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Supabase client for PostgreSQL queries (for Apply API)"""
    
    def __init__(self):
        settings = get_settings()
        # Use either service_key or service_role_key
        service_key = settings.supabase_service_key
        if not service_key and settings.supabase_service_role_key:
            service_key = settings.supabase_service_role_key
        if not service_key:
            raise ValueError("Either SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_ROLE_KEY must be set")
        
        self.client: Client = create_client(
            settings.supabase_url,
            service_key.get_secret_value()
        )
    
    def get_candidate_data(self, cand_id: int) -> Optional[dict]:
        """Fetch candidate data from auto_apply_cand table"""
        try:
            response = self.client.table("auto_apply_cand").select(
                "cand_id, disability_id, veteran_disclosure_id, ethnicity_id, race_id, gender_id, is_remote_preferred, Preferred_MinimumPayrate_PerHour"
            ).eq("cand_id", cand_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching candidate data for cand_id {cand_id}: {str(e)}")
            raise
    
    def get_requirement_remote_flag(self, requirement_id: str) -> Optional[bool]:
        """
        Return is_remote_location flag for a requirement from parsed_requirements.

        Returns:
            True  -> job is remote
            False -> job is explicitly non-remote
            None  -> no row found or flag is NULL (no info)
        """
        try:
            response = (
                self.client.table("parsed_requirements")
                .select("requirement_id, is_remote_location")
                .eq("requirement_id", requirement_id)
                .limit(1)
                .execute()
            )

            if not response.data or len(response.data) == 0:
                return None

            value = response.data[0].get("is_remote_location")
            if value is None:
                return None
            return bool(value)
        except Exception as e:
            logger.error(
                f"Error fetching is_remote_location for requirement_id {requirement_id}: {str(e)}"
            )
            raise
    
    def get_requirement_min_payrate(self, requirement_id: str) -> Optional[float]:
        """
        Return min_payrate for a requirement from parsed_requirements.
        
        Returns:
            float -> job's minimum pay rate
            None  -> no row found or min_payrate is NULL (no info)
        """
        try:
            response = (
                self.client.table("parsed_requirements")
                .select("requirement_id, min_payrate")
                .eq("requirement_id", requirement_id)
                .limit(1)
                .execute()
            )
            
            if not response.data or len(response.data) == 0:
                return None
            
            value = response.data[0].get("min_payrate")
            if value is None:
                return None
            return float(value)
        except Exception as e:
            logger.error(
                f"Error fetching min_payrate for requirement_id {requirement_id}: {str(e)}"
            )
            raise
    
    def insert_application_tracking(
        self, 
        cand_id: int, 
        requirement_id: str, 
        matching_id: Optional[int] = None, 
        similarity_score: Optional[float] = None
    ) -> Optional[dict]:
        """
        Insert or update application tracking record
        
        Uses upsert to handle unique constraint on (cand_id, requirement_id)
        
        Args:
            cand_id: Candidate ID
            requirement_id: Requirement/Job ID
            matching_id: Optional matching ID from cand_job_matching (NULL for manual apply)
            similarity_score: Optional similarity score (NULL for manual apply)
        """
        try:
            from datetime import datetime, timezone
            from postgrest.exceptions import APIError
            
            tracking_data = {
                "cand_id": cand_id,
                "requirement_id": requirement_id,
                "application_status": "MATCHED",
                "applied_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Only include matching_id and similarity_score if provided
            if matching_id is not None:
                tracking_data["matching_id"] = matching_id
            if similarity_score is not None:
                tracking_data["similarity_score"] = similarity_score
            
            # Use upsert to handle unique constraint
            # This will insert if not exists, or update if exists
            response = self.client.table("job_application_tracking").upsert(
                tracking_data,
                on_conflict="cand_id,requirement_id"
            ).execute()
            
            if response.data and len(response.data) > 0:
                logger.info(f"Application tracking record inserted/updated: application_id={response.data[0].get('application_id')}")
                return response.data[0]
            
            logger.warning("Application tracking record insert returned no data")
            return None
            
        except APIError as e:
            # APIError from postgrest - extract error info safely
            error_code = None
            error_message = str(e)
            error_details = None
            
            # Try to extract from args - check if it's a dict
            if e.args and len(e.args) > 0:
                if isinstance(e.args[0], dict):
                    error_code = e.args[0].get('code')
                    error_message = e.args[0].get('message', error_message)
                    error_details = e.args[0].get('details')
                elif isinstance(e.args[0], str):
                    # If it's a string, use it as the message
                    error_message = e.args[0]
            
            if error_code == '23503':  # Foreign key violation
                if error_details:
                    if 'matching_id' in error_details:
                        logger.warning(f"Foreign key constraint violation: matching_id {matching_id} may not exist in cand_job_matching table. {error_message}")
                    elif 'requirement_id' in error_details:
                        logger.warning(f"Foreign key constraint violation: requirement_id {requirement_id} may not exist in parsed_requirements table. {error_message}")
                    else:
                        logger.warning(f"Foreign key constraint violation: {error_message}. Details: {error_details}")
                else:
                    logger.warning(f"Foreign key constraint violation: {error_message}")
            else:
                logger.error(f"Supabase API error inserting application tracking record: {error_message}")
            raise
        except Exception as e:
            logger.error(f"Error inserting application tracking record: {str(e)}")
            raise


class SupabaseRepository:
    """Repository responsible for writing candidate data into Supabase (for Candidate Sync API)"""

    def __init__(self, url: str, service_key: str, table: str = "auto_apply_cand") -> None:
        self._client: Client = create_client(url, service_key)
        self._table = table

    def upsert_candidate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = (
            self._client.table(self._table)
            .upsert(payload, on_conflict="email")
            .execute()
        )
        if response.data:
            return response.data[0]
        return {}


def serialize_candidate(
    *,
    candidate_id: int,
    first_name: Optional[str],
    last_name: Optional[str],
    email: str,
    password: Optional[str],
    birth_date: Optional[date],
    ssn: Optional[str],
    over_18_age: Optional[bool],
    mobile: Optional[str],
    home: Optional[str],
    work: Optional[str],
    work_ext: Optional[str],
    relocation: Optional[bool],
) -> Dict[str, Any]:
    """Prepare a dictionary suitable for Supabase insertion.
    
    Note: cand_id is set from SQL Server's CandidateID to preserve the original ID.
    The upsert is based on email (unique constraint).
    """

    return {
        "cand_id": candidate_id,  # Use CandidateID from SQL Server
        "first_name": first_name or "",
        "last_name": last_name or "",
        "email": email,
        "password": password or "",
        "birth_date": birth_date.isoformat() if birth_date else None,
        "ssn": ssn,
        "over_18_age": over_18_age,
        "mobile": mobile,
        "home": home,
        "work": work,
        "work_ext": work_ext,
        "relocation": relocation,
    }

