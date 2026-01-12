import logging
import asyncio
from typing import Optional
from app.api.apply_webhook.models import CandJobMatching, AutoApplyCand
from app.db.sql_server import SQLServerConnection
from app.supabase.client import SupabaseClient
from app.utils.retry_utils import retry_with_backoff
from config import get_settings
from app.constants import SIMILARITY_THRESHOLD, DEFAULT_DAILY_LIMIT

logger = logging.getLogger(__name__)


class WebhookProcessingService:
    """Service to process Supabase webhook events"""
    
    def __init__(self):
        self.supabase = SupabaseClient()
        self.sql_server = SQLServerConnection()
    
    async def process_webhook(self, webhook_data: dict) -> dict:
        """
        Process webhook event from Supabase
        
        Args:
            webhook_data: Webhook payload from Supabase
            
        Returns:
            dict: Processing result
        """
        try:
            settings = get_settings()
            
            # Validate webhook type
            if webhook_data.get("type") != "INSERT":
                return {
                    "success": False,
                    "message": f"Webhook type {webhook_data.get('type')} not supported. Only INSERT events are processed."
                }
            
            # Validate table name
            if webhook_data.get("table") != "cand_job_matching":
                return {
                    "success": False,
                    "message": f"Table {webhook_data.get('table')} not supported. Only cand_job_matching table is processed."
                }
            
            # Extract record data
            record = webhook_data.get("record")
            if not record:
                return {
                    "success": False,
                    "message": "No record data found in webhook payload"
                }
            
            # Parse the matching record
            matching = CandJobMatching(**record)
            
            # Check similarity score condition
            if matching.similarity_score is None or matching.similarity_score < SIMILARITY_THRESHOLD:
                return {
                    "success": False,
                    "message": f"Similarity score {matching.similarity_score} is below threshold {SIMILARITY_THRESHOLD}. Skipping stored procedure execution.",
                    "similarity_score": matching.similarity_score
                }
            
            logger.info(f"Processing match with similarity_score {matching.similarity_score} for cand_id={matching.cand_id}, requirement_id={matching.requirement_id}")
            
            # Check if application already exists (prevents duplicate + saves limit)
            existing_app = await retry_with_backoff(
                asyncio.to_thread,
                self.supabase.check_existing_application,
                matching.cand_id,
                matching.requirement_id,
                max_retries=settings.retry_max_attempts,
                initial_delay=settings.retry_initial_delay,
                max_delay=settings.retry_max_delay,
                exponential_base=settings.retry_exponential_base
            )
            
            if existing_app:
                logger.info(
                    f"Application already exists for cand_id={matching.cand_id}, "
                    f"requirement_id={matching.requirement_id}, "
                    f"application_id={existing_app.get('application_id')}"
                )
                return {
                    "success": False,
                    "message": "Application already exists for this job",
                    "reason": "duplicate_application",
                    "cand_id": matching.cand_id,
                    "requirement_id": matching.requirement_id,
                    "existing_application_id": existing_app.get('application_id'),
                    "existing_status": existing_app.get('application_status')
                }
            
            # Get candidate preferences (creates default if not exists)
            from app.services.auto_apply_preferences import get_candidate_preferences, check_daily_limit_reached
            
            preferences = await get_candidate_preferences(matching.cand_id)
            
            # Check if auto-apply is active for this candidate
            if not preferences.get('is_active', True):
                logger.info(f"Auto-apply is disabled for cand_id={matching.cand_id}")
                return {
                    "success": False,
                    "message": "Auto-apply is disabled for this candidate",
                    "reason": "auto_apply_disabled",
                    "cand_id": matching.cand_id,
                    "requirement_id": matching.requirement_id
                }
            
            # Check daily application limit
            daily_limit = preferences.get('daily_application_limit', DEFAULT_DAILY_LIMIT)
            limit_reached, applications_today = await check_daily_limit_reached(
                matching.cand_id,
                daily_limit
            )
            
            if limit_reached:
                logger.info(
                    f"Daily limit reached for cand_id={matching.cand_id}: "
                    f"{applications_today}/{daily_limit} applications today"
                )
                return {
                    "success": False,
                    "message": f"Daily application limit reached ({applications_today}/{daily_limit})",
                    "reason": "daily_limit_reached",
                    "cand_id": matching.cand_id,
                    "requirement_id": matching.requirement_id,
                    "daily_limit": daily_limit,
                    "applications_today": applications_today
                }
            
            logger.info(
                f"Daily limit check passed for cand_id={matching.cand_id}: "
                f"{applications_today}/{daily_limit} applications today"
            )
            
            # Fetch candidate data from auto_apply_cand table (async with retry)
            candidate_data = await retry_with_backoff(
                asyncio.to_thread,
                self.supabase.get_candidate_data,
                matching.cand_id,
                max_retries=settings.retry_max_attempts,
                initial_delay=settings.retry_initial_delay,
                max_delay=settings.retry_max_delay,
                exponential_base=settings.retry_exponential_base
            )
            if not candidate_data:
                return {
                    "success": False,
                    "message": f"Candidate with cand_id {matching.cand_id} not found in auto_apply_cand table"
                }
            
            candidate = AutoApplyCand(**candidate_data)

            # Remote preference filter
            # Treat missing flag as False (no preference)
            is_remote_preferred = bool(candidate_data.get("is_remote_preferred") or False)
            
            # Pay rate filter
            # Get candidate's preferred minimum pay rate
            candidate_min_payrate = candidate_data.get("Preferred_MinimumPayrate_PerHour")

            # Prepare async tasks for parallel execution
            remote_check_coro = None
            if is_remote_preferred:
                remote_check_coro = retry_with_backoff(
                    asyncio.to_thread,
                    self.supabase.get_requirement_remote_flag,
                    matching.requirement_id,
                    max_retries=settings.retry_max_attempts,
                    initial_delay=settings.retry_initial_delay,
                    max_delay=settings.retry_max_delay,
                    exponential_base=settings.retry_exponential_base,
                )

            payrate_check_coro = None
            if candidate_min_payrate is not None:
                payrate_check_coro = retry_with_backoff(
                    asyncio.to_thread,
                    self.supabase.get_requirement_min_payrate,
                    matching.requirement_id,
                    max_retries=settings.retry_max_attempts,
                    initial_delay=settings.retry_initial_delay,
                    max_delay=settings.retry_max_delay,
                    exponential_base=settings.retry_exponential_base,
                )

            # Execute enabled checks in parallel
            # Use asyncio.sleep(0) as placeholder for skipped tasks to maintain index alignment
            check_results = await asyncio.gather(
                remote_check_coro if remote_check_coro else asyncio.sleep(0),
                payrate_check_coro if payrate_check_coro else asyncio.sleep(0)
            )

            # Process Remote Check Result
            if is_remote_preferred:
                is_remote_location = check_results[0]
                # Rule: True -> remote, False -> non-remote, None -> unknown
                if is_remote_location is False:
                    logger.info(
                        f"Skipping apply for cand_id={matching.cand_id}, requirement_id={matching.requirement_id} "
                        f"because candidate prefers remote but job is not remote."
                    )
                    return {
                        "success": False,
                        "message": "Candidate prefers remote but job is not remote. Skipping application.",
                        "cand_id": matching.cand_id,
                        "requirement_id": matching.requirement_id,
                        "similarity_score": matching.similarity_score,
                    }

            # Process Payrate Check Result
            if candidate_min_payrate is not None:
                job_min_payrate = check_results[1]
                # Rule: Skip if job pay < candidate preference
                if job_min_payrate is not None and job_min_payrate < candidate_min_payrate:
                    logger.info(
                        f"Skipping apply for cand_id={matching.cand_id}, requirement_id={matching.requirement_id} "
                        f"because job min_payrate ({job_min_payrate}) is less than candidate's preferred minimum ({candidate_min_payrate})."
                    )
                    return {
                        "success": False,
                        "message": f"Job minimum pay rate ({job_min_payrate}) is below candidate's preferred minimum ({candidate_min_payrate}). Skipping application.",
                        "cand_id": matching.cand_id,
                        "requirement_id": matching.requirement_id,
                        "similarity_score": matching.similarity_score,
                        "job_min_payrate": job_min_payrate,
                        "candidate_preferred_min_payrate": candidate_min_payrate,
                    }
            
            # Prepare stored procedure parameters
            sp_params = {
                'CandidateID': matching.cand_id,
                'RequirementID': int(matching.requirement_id),  # Convert requirement_id to int
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
            
            # Insert into job_application_tracking table after successful SP execution (async with retry)
            tracking_record = None
            try:
                tracking_record = await retry_with_backoff(
                    asyncio.to_thread,
                    self.supabase.insert_application_tracking,
                    matching.cand_id,
                    matching.requirement_id,
                    matching.matching_id,
                    matching.similarity_score,
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
                "message": "Stored procedure executed successfully",
                "matching_id": matching.matching_id,
                "cand_id": matching.cand_id,
                "requirement_id": matching.requirement_id,
                "similarity_score": matching.similarity_score,
                "selection_id": selection_id,
                "application_id": tracking_record.get('application_id') if tracking_record else None
            }
            
        except ValueError as e:
            logger.error(f"Validation error processing webhook: {str(e)}")
            return {
                "success": False,
                "message": f"Validation error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
            return {
                "success": False,
                "message": f"Error processing webhook: {str(e)}"
            }

