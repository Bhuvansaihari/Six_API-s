"""
Business logic for Manual Apply API.
"""
import logging
import asyncio
from typing import Optional
from app.api.apply_webhook.models import AutoApplyCand
from app.db.sql_server import SQLServerConnection
from app.supabase.client import SupabaseClient
from app.utils.retry_utils import retry_with_backoff
from config import get_settings

logger = logging.getLogger(__name__)


class ManualApplyService:
    """Service to manually apply candidate to job"""
    
    def __init__(self):
        self.supabase = SupabaseClient()
        self.sql_server = SQLServerConnection()
    
    async def apply_candidate_to_job(
        self, 
        cand_id: int, 
        requirement_id: int
    ) -> dict:
        """
        Manually apply a candidate to a job requirement
        
        Args:
            cand_id: Candidate ID
            requirement_id: Requirement/Job ID
            
        Returns:
            dict: Processing result
        """
        try:
            settings = get_settings()
            
            logger.info(f"Processing manual application for cand_id={cand_id}, requirement_id={requirement_id}")
            
            # Fetch candidate data from auto_apply_cand table (async with retry)
            candidate_data = await retry_with_backoff(
                asyncio.to_thread,
                self.supabase.get_candidate_data,
                cand_id,
                max_retries=settings.retry_max_attempts,
                initial_delay=settings.retry_initial_delay,
                max_delay=settings.retry_max_delay,
                exponential_base=settings.retry_exponential_base
            )
            
            if not candidate_data:
                return {
                    "success": False,
                    "message": f"Candidate with cand_id {cand_id} not found in auto_apply_cand table"
                }
            
            candidate = AutoApplyCand(**candidate_data)
            
            # Prepare stored procedure parameters
            sp_params = {
                'CandidateID': cand_id,
                'RequirementID': requirement_id,
                'DisabilityID': candidate.disability_id or 0,
                'VeteranDisclosureID': candidate.veteran_disclosure_id or 0,
                'EthnicityID': candidate.ethnicity_id or 0,
                'HumanRaceID': candidate.race_id or 0,
                'GenderID': candidate.gender_id or 0,
                'FileName': None,
                'FileExtension': None,
                'FileType': None,
                'FileContent': None,
                'ResumeID': 0,
                'ServedAsTxnsJson': None,
                'ReqTalentChannelID': 0
            }
            
            # Execute stored procedure (async with retry)
            selection_id = await retry_with_backoff(
                asyncio.to_thread,
                self.sql_server.execute_stored_procedure,
                sp_params,
                max_retries=settings.retry_max_attempts,
                initial_delay=settings.retry_initial_delay,
                max_delay=settings.retry_max_delay,
                exponential_base=settings.retry_exponential_base
            )
            
            # Insert into job_application_tracking table (with NULL matching_id and similarity_score)
            tracking_record = None
            try:
                tracking_record = await retry_with_backoff(
                    asyncio.to_thread,
                    self.supabase.insert_application_tracking,
                    cand_id,
                    str(requirement_id),  # Convert to string as per schema
                    None,  # matching_id = NULL for manual apply
                    None,  # similarity_score = NULL for manual apply
                    max_retries=settings.retry_max_attempts,
                    initial_delay=settings.retry_initial_delay,
                    max_delay=settings.retry_max_delay,
                    exponential_base=settings.retry_exponential_base
                )
                
                logger.info(f"Application tracking record created: application_id={tracking_record.get('application_id') if tracking_record else 'N/A'}")
            except Exception as e:
                # Log error but don't fail the entire process
                # The stored procedure already executed successfully
                logger.error(f"Failed to insert application tracking record: {str(e)}", exc_info=True)
            
            return {
                "success": True,
                "message": "Job application submitted successfully",
                "cand_id": cand_id,
                "requirement_id": requirement_id,
                "selection_id": selection_id,
                "application_id": tracking_record.get('application_id') if tracking_record else None
            }
            
        except ValueError as e:
            logger.error(f"Validation error processing manual application: {str(e)}")
            return {
                "success": False,
                "message": f"Validation error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error processing manual application: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Error processing application: {str(e)}"
            }

