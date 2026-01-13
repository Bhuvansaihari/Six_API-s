"""
Database service module for executing stored procedures in Job List API.

This module provides async functions to execute SQL Server stored procedures
and handle result set processing for the Browse Job List feature.
It reuses the connection pool from the Recommendations API for efficiency.
"""

import pyodbc
import asyncio
import logging
from typing import List, Dict, Any, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError
)
# Reusing the connection pool from Recommendations API as requested
from app.services.recommendations.db_pool import get_db_pool
from app.services.recommendations.database_service import (
    DatabaseConnectionError,
    DatabaseQueryError,
    _is_retryable_error,
    _serialize_value
)
from config import get_settings

# Configure logging
logger = logging.getLogger(__name__)


def _map_job_list_result_keys(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map stored procedure result keys to clean API response keys for job list endpoint.
    """
    key_mapping = {
        "RequirementID": "requirement_id",
        "JobTitleText": "job_title",
        "Location": "location",
        "SourceID": "source_id",
        "JobTypeText": "job_type",
        "ClientName": "client_name",
        "CreatedDate": "created_at",
        "PayRateToCandidate": "pay_rate",
        "TotalCount": "total_count"
    }
    
    mapped_result = {}
    for key, value in result.items():
        if key in key_mapping:
            mapped_key = key_mapping[key]
            mapped_result[mapped_key] = value
    
    return mapped_result


async def execute_job_list_stored_procedure(
    candidate_id: int
) -> tuple[List[Dict[str, Any]], Optional[int]]:
    """
    Execute the USP_AI_Get_JobList stored procedure.
    
    This function executes the stored procedure asynchronously with retry logic
    for transient failures and returns the results with clean key names.
    
    Returns:
        tuple: (mapped_results, total_count)
    """
    if not candidate_id or candidate_id <= 0:
        raise ValueError("candidate_id must be a positive integer")
    
    logger.info(f"Executing job list stored procedure for candidate_id={candidate_id}")
    
    settings = get_settings()
    # Reuse the existing recommendations DB pool
    db_pool = await get_db_pool()
    loop = asyncio.get_event_loop()
    
    # Retry decorator for transient database errors
    @retry(
        stop=stop_after_attempt(settings.recommendations_db_retry_attempts),
        wait=wait_exponential(multiplier=1, min=settings.recommendations_db_retry_delay, max=10),
        retry=retry_if_exception_type((pyodbc.Error, DatabaseConnectionError)),
        reraise=True
    )
    async def _execute_with_retry():
        """Execute stored procedure with retry logic."""
        conn = await db_pool.get_connection()
        try:
            def _execute():
                """Internal function to execute stored procedure synchronously."""
                cursor = None
                try:
                    cursor = conn.cursor()
                    
                    logger.debug(f"Executing stored procedure USP_AI_Get_JobList with candidate_id={candidate_id}")
                    
                    cursor.execute(
                        """
                        EXEC [dbo].[USP_AI_Get_JobList]
                            @CandidateID = ?
                        """,
                        (candidate_id,)
                    )
                    
                    results = []
                    
                    # Process all result sets
                    while True:
                        if cursor.description:
                            logger.debug(f"Processing result set with {len(cursor.description)} columns")
                            rows = cursor.fetchall()
                            logger.debug(f"Fetched {len(rows)} rows from current result set")
                            for row in rows:
                                # Convert row to dict first using serialize helper
                                row_dict = {
                                    col[0]: row[idx] 
                                    for idx, col in enumerate(cursor.description)
                                    if row[idx] is not None  # Include None values? Check serializer
                                }
                                # Use helper from re-used module (checking serialization logic)
                                # Actually, better to define internal conversion similar to recomm service
                                results.append({k: _serialize_value(v) for k, v in row_dict.items()})
                        
                        # Try to move to next result set
                        try:
                            if not cursor.nextset():
                                break
                        except pyodbc.Error as e:
                            # HY000 error on nextset() after last result set is expected in some drivers
                            error_code = e.args[0] if e.args else None
                            if error_code == 'HY000':
                                break
                            else:
                                raise
                    
                    logger.info(f"Job list stored procedure executed successfully. Returned {len(results)} records")
                    return results
                    
                except pyodbc.Error as e:
                    # Log and re-raise to be caught by wrapper
                    logger.error(f"Database error executing stored procedure: {e}")
                    raise
                
                finally:
                    if cursor is not None:
                        try:
                            cursor.close()
                        except Exception:
                            pass
            
            results = await loop.run_in_executor(None, _execute)
            return results
        
        finally:
            await db_pool.return_connection(conn)
    
    try:
        results = await _execute_with_retry()
        
        # Extract total_count from first record before mapping
        total_count = None
        if results:
            first_result = results[0]
            if "TotalCount" in first_result:
                total_count = first_result.get("TotalCount")
            elif "totalCount" in first_result:
                total_count = first_result.get("totalCount")
        
        # Map results to clean API keys
        mapped_results = [_map_job_list_result_keys(result) for result in results]
        
        return mapped_results, total_count
        
    except RetryError as e:
        logger.error(f"All retry attempts exhausted for candidate_id={candidate_id}: {e}")
        raise DatabaseConnectionError(
            f"Failed to execute stored procedure after {settings.recommendations_db_retry_attempts} attempts: {e}"
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error in execute_job_list_stored_procedure: {e}", exc_info=True)
        # If it's already a wrapped error, re-raise, else wrap it
        if isinstance(e, (DatabaseConnectionError, DatabaseQueryError)):
            raise
        raise DatabaseQueryError(f"Unexpected error: {e}") from e
