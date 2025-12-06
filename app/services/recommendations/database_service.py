"""
Database service module for executing stored procedures in Recommendations API.

This module provides async functions to execute SQL Server stored procedures
and handle result set processing.
"""

import pyodbc
import asyncio
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, date
from decimal import Decimal
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError
)
from app.services.recommendations.db_pool import get_db_pool
from config import get_settings

# Configure logging
logger = logging.getLogger(__name__)


def _serialize_value(value: Any) -> Any:
    """
    Serialize a value to a JSON-compatible format.
    
    Converts datetime, date, and Decimal objects to strings/numbers.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, date):
        return value.isoformat()
    elif isinstance(value, Decimal):
        return float(value)
    elif value is None:
        return None
    else:
        return value


def _convert_row_to_dict(cursor: pyodbc.Cursor, row: pyodbc.Row) -> Dict[str, Any]:
    """Convert a pyodbc row to a dictionary with JSON-serializable values."""
    columns = [column[0] for column in cursor.description]
    row_dict = dict(zip(columns, row))
    return {key: _serialize_value(value) for key, value in row_dict.items()}


def _map_result_keys(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map stored procedure result keys to clean API response keys.
    Only returns the fields specified in the key mapping.
    """
    key_mapping = {
        "JobTitleText": "Jobtitle",
        "RequirementJobDescription": "JobDescription",
        "RequirementDuration": "Duration",
        "CategoryName": "Category",
        "JobTypeText": "JobType",
        "RemoteOptionType": "Remote/On-site",
        "ClientName": "Client",
        "Location": "Location"
    }
    
    mapped_result = {}
    for key, value in result.items():
        if key in key_mapping:
            mapped_key = key_mapping[key]
            mapped_result[mapped_key] = value
    
    return mapped_result


# Define custom exceptions for better error handling
class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""
    pass


class DatabaseQueryError(Exception):
    """Raised when database query execution fails."""
    pass


class DatabaseTimeoutError(Exception):
    """Raised when database operation times out."""
    pass


def _is_retryable_error(exception: Exception) -> bool:
    """Determine if an exception is retryable."""
    if isinstance(exception, pyodbc.Error):
        error_code = getattr(exception, 'args', [None])[0] if exception.args else None
        
        retryable_codes = [
            '08S01',  # Communication link failure
            '40001',  # Serialization failure
            '40003',  # Statement completion unknown
            '40P01',  # Deadlock detected
            'HY000',  # General error (check message)
        ]
        
        if error_code in retryable_codes:
            return True
        
        error_msg = str(exception).lower()
        transient_keywords = [
            'timeout',
            'connection',
            'network',
            'deadlock',
            'temporary',
            'retry',
            'lost connection'
        ]
        
        if any(keyword in error_msg for keyword in transient_keywords):
            return True
    
    return False


async def execute_stored_procedure(
    candidate_id: int,
    page_no: int = 1,
    page_size: int = 10,
    job_activity_type_id: int = 0
) -> List[Dict[str, Any]]:
    """
    Execute the USP_SC_Get_JobSeekerRecommenededJobList stored procedure.
    
    This function executes the stored procedure asynchronously with retry logic
    for transient failures and returns the results with clean key names mapped
    according to the API specification.
    """
    if not candidate_id or candidate_id <= 0:
        raise ValueError("candidate_id must be a positive integer")
    
    logger.info(
        f"Executing stored procedure for candidate_id={candidate_id}, "
        f"page_no={page_no}, page_size={page_size}, job_activity_type_id={job_activity_type_id}"
    )
    
    settings = get_settings()
    db_pool = get_db_pool()
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
        async with db_pool.get_connection() as conn:
            def _execute():
                """Internal function to execute stored procedure synchronously."""
                try:
                    cursor = conn.cursor()
                    
                    cursor.execute(
                        """
                        EXEC [dbo].[USP_SC_Get_JobSeekerRecommenededJobList]
                            @PageNo = ?,
                            @PageSize = ?,
                            @CandidateID = ?,
                            @JobActivityTypeID = ?
                        """,
                        (page_no, page_size, candidate_id, job_activity_type_id)
                    )
                    
                    results = []
                    
                    while True:
                        if cursor.description:
                            rows = cursor.fetchall()
                            for row in rows:
                                results.append(_convert_row_to_dict(cursor, row))
                        
                        if not cursor.nextset():
                            break
                    
                    cursor.close()
                    logger.info(f"Stored procedure executed successfully. Returned {len(results)} records")
                    return results
                    
                except pyodbc.OperationalError as e:
                    logger.warning(f"Operational error executing stored procedure: {e}")
                    if _is_retryable_error(e):
                        raise DatabaseConnectionError(f"Transient database error: {e}") from e
                    raise DatabaseQueryError(f"Database operational error: {e}") from e
                    
                except pyodbc.ProgrammingError as e:
                    logger.error(f"Programming error executing stored procedure: {e}")
                    raise DatabaseQueryError(f"Database programming error: {e}") from e
                    
                except pyodbc.DatabaseError as e:
                    logger.error(f"Database error executing stored procedure: {e}")
                    if _is_retryable_error(e):
                        raise DatabaseConnectionError(f"Transient database error: {e}") from e
                    raise DatabaseQueryError(f"Database error: {e}") from e
                    
                except pyodbc.Error as e:
                    logger.error(f"PyODBC error executing stored procedure: {e}")
                    if _is_retryable_error(e):
                        raise DatabaseConnectionError(f"Transient database error: {e}") from e
                    raise DatabaseQueryError(f"Database error: {e}") from e
                    
                except Exception as e:
                    logger.error(f"Unexpected error executing stored procedure: {e}", exc_info=True)
                    raise DatabaseQueryError(f"Unexpected error: {e}") from e
            
            results = await loop.run_in_executor(None, _execute)
            return results
    
    try:
        results = await _execute_with_retry()
        mapped_results = [_map_result_keys(result) for result in results]
        return mapped_results
        
    except RetryError as e:
        logger.error(f"All retry attempts exhausted for candidate_id={candidate_id}: {e}")
        raise DatabaseConnectionError(
            f"Failed to execute stored procedure after {settings.recommendations_db_retry_attempts} attempts: {e}"
        ) from e
    except (DatabaseConnectionError, DatabaseQueryError) as e:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in execute_stored_procedure: {e}", exc_info=True)
        raise DatabaseQueryError(f"Unexpected error: {e}") from e


async def get_recommendations(
    candidate_id: int,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Get job recommendations for a candidate with optional caching.
    
    This is the main function to retrieve job recommendations. It handles
    caching, executes the stored procedure, and returns formatted results.
    """
    # Constants as specified
    PAGE_NO = 1
    PAGE_SIZE = 10
    JOB_ACTIVITY_TYPE_ID = 0
    
    # Check cache if enabled
    if use_cache:
        from app.services.recommendations.cache_manager import get_cache_manager
        cache = get_cache_manager()
        cached_result = cache.get(candidate_id, PAGE_NO, PAGE_SIZE, JOB_ACTIVITY_TYPE_ID)
        
        if cached_result is not None:
            logger.info(f"Returning cached results for candidate_id={candidate_id}")
            return cached_result
    
    # Execute stored procedure
    recommendations = await execute_stored_procedure(
        candidate_id=candidate_id,
        page_no=PAGE_NO,
        page_size=PAGE_SIZE,
        job_activity_type_id=JOB_ACTIVITY_TYPE_ID
    )
    
    # Extract total count from first record if available
    total_count = None
    if recommendations:
        first_record = recommendations[0]
        if "TotalCount" in first_record:
            total_count = first_record.get("TotalCount")
            for record in recommendations:
                record.pop("TotalCount", None)
        elif "totalCount" in first_record:
            total_count = first_record.get("totalCount")
            for record in recommendations:
                record.pop("totalCount", None)
    
    # Build response
    response = {
        "candidate_id": candidate_id,
        "recommendations": recommendations,
        "total_count": total_count,
        "page_no": PAGE_NO,
        "page_size": PAGE_SIZE
    }
    
    # Cache the result if caching is enabled
    if use_cache:
        from app.services.recommendations.cache_manager import get_cache_manager
        cache = get_cache_manager()
        cache.set(candidate_id, PAGE_NO, PAGE_SIZE, JOB_ACTIVITY_TYPE_ID, response)
    
    return response

