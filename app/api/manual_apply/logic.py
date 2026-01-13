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
                    applied_via_agent=False,  # Set applied_via_agent=False for manual applications
                    max_retries=settings.retry_max_attempts,
                    initial_delay=settings.retry_initial_delay,
                    max_delay=settings.retry_max_delay,
                    exponential_base=settings.retry_exponential_base
                )
                
                logger.info(f"Application tracking record created: application_id={tracking_record.get('application_id') if tracking_record else 'N/A'}")
            
            except Exception as e:
                # Check for Foreign Key Violation (Code 23503)
                # Check both structured args and string representation for robustness
                is_fk_violation = False
                
                # Debug logging to help diagnose why it wasn't caught before
                # logger.warning(f"Lazy Sync Debug: Checking error: {type(e)} {e.args}")

                if '23503' in str(e) or (e.args and isinstance(e.args[0], dict) and e.args[0].get('code') == '23503'):
                    is_fk_violation = True
                
                if is_fk_violation:
                    logger.warning(f"Lazy Sync: Requirement {requirement_id} missing in Supabase. Attempting auto-sync...")
                    try:
                        # 1. Fetch minimal details from SQL Server
                        req_details = await asyncio.to_thread(self.sql_server.fetch_requirement_details, requirement_id)
                        
                        if req_details:
                            # 2. Insert Stub into Supabase
                            stub_success = await asyncio.to_thread(self.supabase.insert_parsed_requirement_stub, req_details)
                            
                            if stub_success:
                                # 3. Retry Tracking Insert
                                tracking_record = await retry_with_backoff(
                                    asyncio.to_thread,
                                    self.supabase.insert_application_tracking,
                                    cand_id,
                                    str(requirement_id),
                                    None,
                                    None,
                                    applied_via_agent=False, # Pass usage flag in retry too
                                    max_retries=1  # Only retry once
                                )
                                logger.info("Lazy Sync Successful: Tracking record inserted.")
                            else:
                                logger.warning("Lazy Sync: Failed to insert stub record.")
                        else:
                            logger.warning("Lazy Sync: Requirement details not found in SQL Server.")
                            
                    except Exception as sync_e:
                        logger.error(f"Lazy Sync Exception: {str(sync_e)}")
                
                # If still no tracking record, log the original error
                if not tracking_record:
                    # Don't fail the request, just log
                    logger.error(f"Failed to insert application tracking record: {str(e)}")
            
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

