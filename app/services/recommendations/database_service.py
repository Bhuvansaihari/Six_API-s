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


def _map_list_result_keys(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map stored procedure result keys to clean API response keys for list endpoint.
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


def _map_details_result_keys(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map stored procedure result keys to clean API response keys for details endpoint.
    """
    key_mapping = {
        "JobTitleText": "job_title",
        "RequirementJobDescription": "job_description",
        "CategoryName": "category",
        "JobTypeText": "job_type",
        "RemoteOptionType": "remote_option",
        "RequirementID": "requirement_id",
        "DepartmentName": "department",
        "ClientName": "client_name",
        "Location": "location",
        "CityName": "city",
        "StateShortName": "state",
        "PayRateToCandidate": "pay_rate_to_candidate",
        "BillRateFromClient": "bill_rate_from_client",
        "CreatedDate": "created_date",
        "ClientID": "client_id"
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


async def execute_list_stored_procedure(
    candidate_id: int
) -> tuple[List[Dict[str, Any]], Optional[int]]:
    """
    Execute the USP_AI_Get_JobSeekerRecommenededJobList stored procedure.
    
    This function executes the stored procedure asynchronously with retry logic
    for transient failures and returns the results with clean key names.
    
    Returns:
        tuple: (mapped_results, total_count)
    """
    if not candidate_id or candidate_id <= 0:
        raise ValueError("candidate_id must be a positive integer")
    
    logger.info(f"Executing list stored procedure for candidate_id={candidate_id}")
    
    settings = get_settings()
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
                    
                    logger.debug(f"Executing stored procedure USP_AI_Get_JobSeekerRecommenededJobList with candidate_id={candidate_id}")
                    
                    cursor.execute(
                        """
                        EXEC [dbo].[USP_AI_Get_JobSeekerRecommenededJobList]
                            @CandidateID = ?
                        """,
                        (candidate_id,)
                    )
                    
                    results = []
                    
                    # Process all result sets
                    # Note: SQL Server stored procedures may raise HY000 on nextset() after the last result set
                    # This is expected behavior and should be handled gracefully
                    while True:
                        if cursor.description:
                            logger.debug(f"Processing result set with {len(cursor.description)} columns")
                            rows = cursor.fetchall()
                            logger.debug(f"Fetched {len(rows)} rows from current result set")
                            for row in rows:
                                results.append(_convert_row_to_dict(cursor, row))
                        
                        # Try to move to next result set
                        # SQL Server may raise HY000 error here after the last result set
                        try:
                            if not cursor.nextset():
                                break
                        except pyodbc.Error as e:
                            # HY000 error on nextset() after last result set is expected
                            error_code = e.args[0] if e.args else None
                            if error_code == 'HY000':
                                logger.debug("Reached end of result sets (HY000 on nextset - expected)")
                                break
                            else:
                                # Re-raise if it's a different error
                                raise
                    
                    logger.info(f"List stored procedure executed successfully. Returned {len(results)} records")
                    return results
                    
                except pyodbc.OperationalError as e:
                    error_code = e.args[0] if e.args else 'UNKNOWN'
                    error_msg = e.args[1] if len(e.args) > 1 else str(e)
                    logger.error(f"Operational error executing stored procedure")
                    logger.error(f"Error Code: {error_code}")
                    logger.error(f"Error Message: {error_msg}")
                    logger.error(f"Candidate ID: {candidate_id}")
                    if _is_retryable_error(e):
                        raise DatabaseConnectionError(f"Transient database error: {e}") from e
                    raise DatabaseQueryError(f"Database operational error: {e}") from e
                    
                except pyodbc.ProgrammingError as e:
                    error_code = e.args[0] if e.args else 'UNKNOWN'
                    error_msg = e.args[1] if len(e.args) > 1 else str(e)
                    logger.error(f"Programming error executing stored procedure")
                    logger.error(f"Error Code: {error_code}")
                    logger.error(f"Error Message: {error_msg}")
                    logger.error(f"Candidate ID: {candidate_id}")
                    raise DatabaseQueryError(f"Database programming error: {e}") from e
                    
                except pyodbc.DatabaseError as e:
                    error_code = e.args[0] if e.args else 'UNKNOWN'
                    error_msg = e.args[1] if len(e.args) > 1 else str(e)
                    logger.error(f"Database error executing stored procedure")
                    logger.error(f"Error Code: {error_code}")
                    logger.error(f"Error Message: {error_msg}")
                    logger.error(f"Candidate ID: {candidate_id}")
                    if _is_retryable_error(e):
                        raise DatabaseConnectionError(f"Transient database error: {e}") from e
                    raise DatabaseQueryError(f"Database error: {e}") from e
                    
                except pyodbc.Error as e:
                    error_code = e.args[0] if e.args else 'UNKNOWN'
                    error_msg = e.args[1] if len(e.args) > 1 else str(e)
                    logger.error(f"PyODBC error executing stored procedure")
                    logger.error(f"Error Code: {error_code}")
                    logger.error(f"Error Message: {error_msg}")
                    logger.error(f"Full exception: {repr(e)}")
                    logger.error(f"Candidate ID: {candidate_id}")
                    if _is_retryable_error(e):
                        raise DatabaseConnectionError(f"Transient database error: {e}") from e
                    raise DatabaseQueryError(f"Database error: {e}") from e
                    
                except Exception as e:
                    logger.error(f"Unexpected error executing stored procedure: {e}", exc_info=True)
                    logger.error(f"Exception type: {type(e).__name__}")
                    logger.error(f"Candidate ID: {candidate_id}")
                    raise DatabaseQueryError(f"Unexpected error: {e}") from e
                
                finally:
                    # Ensure cursor is always closed
                    if cursor is not None:
                        try:
                            cursor.close()
                            logger.debug("Cursor closed successfully")
                        except Exception as e:
                            logger.warning(f"Error closing cursor: {e}")
            
            results = await loop.run_in_executor(None, _execute)
            return results
        
        finally:
            # Return connection to pool
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
        mapped_results = [_map_list_result_keys(result) for result in results]
        
        return mapped_results, total_count
        
    except RetryError as e:
        logger.error(f"All retry attempts exhausted for candidate_id={candidate_id}: {e}")
        raise DatabaseConnectionError(
            f"Failed to execute stored procedure after {settings.recommendations_db_retry_attempts} attempts: {e}"
        ) from e
    except (DatabaseConnectionError, DatabaseQueryError) as e:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in execute_list_stored_procedure: {e}", exc_info=True)
        raise DatabaseQueryError(f"Unexpected error: {e}") from e


async def execute_details_stored_procedure(
    requirement_id: int,
    source_id: int
) -> Optional[Dict[str, Any]]:
    """
    Execute the USP_AI_Get_JobSeekerRecommenededJobDetails stored procedure.
    
    This function executes the stored procedure asynchronously with retry logic
    for transient failures and returns the result with clean key names.
    
    Returns None if no result found (empty result).
    """
    if not requirement_id or requirement_id <= 0:
        raise ValueError("requirement_id must be a positive integer")
    if source_id not in [1, 2]:
        raise ValueError("source_id must be 1 (TA) or 2 (DE)")
    
    logger.info(f"Executing details stored procedure for requirement_id={requirement_id}, source_id={source_id}")
    
    settings = get_settings()
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
                    
                    logger.debug(f"Executing stored procedure USP_AI_Get_JobSeekerRecommenededJobDetails with requirement_id={requirement_id}, source_id={source_id}")
                    
                    cursor.execute(
                        """
                        EXEC [dbo].[USP_AI_Get_JobSeekerRecommenededJobDetails]
                            @RequirementID = ?,
                            @SourceID = ?
                        """,
                        (requirement_id, source_id)
                    )
                    
                    results = []
                    
                    # Process all result sets
                    # Note: SQL Server stored procedures may raise HY000 on nextset() after the last result set
                    # This is expected behavior and should be handled gracefully
                    while True:
                        if cursor.description:
                            logger.debug(f"Processing result set with {len(cursor.description)} columns")
                            rows = cursor.fetchall()
                            logger.debug(f"Fetched {len(rows)} rows from current result set")
                            for row in rows:
                                results.append(_convert_row_to_dict(cursor, row))
                        
                        # Try to move to next result set
                        # SQL Server may raise HY000 error here after the last result set
                        try:
                            if not cursor.nextset():
                                break
                        except pyodbc.Error as e:
                            # HY000 error on nextset() after last result set is expected
                            error_code = e.args[0] if e.args else None
                            if error_code == 'HY000':
                                logger.debug("Reached end of result sets (HY000 on nextset - expected)")
                                break
                            else:
                                # Re-raise if it's a different error
                                raise
                    
                    if not results:
                        logger.info(f"Details stored procedure returned no results for requirement_id={requirement_id}, source_id={source_id}")
                        return None
                    
                    logger.info(f"Details stored procedure executed successfully. Returned 1 record")
                    return results[0]  # Return first (and should be only) result
                    
                except pyodbc.OperationalError as e:
                    error_code = e.args[0] if e.args else 'UNKNOWN'
                    error_msg = e.args[1] if len(e.args) > 1 else str(e)
                    logger.error(f"Operational error executing stored procedure")
                    logger.error(f"Error Code: {error_code}")
                    logger.error(f"Error Message: {error_msg}")
                    logger.error(f"Requirement ID: {requirement_id}, Source ID: {source_id}")
                    if _is_retryable_error(e):
                        raise DatabaseConnectionError(f"Transient database error: {e}") from e
                    raise DatabaseQueryError(f"Database operational error: {e}") from e
                    
                except pyodbc.ProgrammingError as e:
                    error_code = e.args[0] if e.args else 'UNKNOWN'
                    error_msg = e.args[1] if len(e.args) > 1 else str(e)
                    logger.error(f"Programming error executing stored procedure")
                    logger.error(f"Error Code: {error_code}")
                    logger.error(f"Error Message: {error_msg}")
                    logger.error(f"Requirement ID: {requirement_id}, Source ID: {source_id}")
                    raise DatabaseQueryError(f"Database programming error: {e}") from e
                    
                except pyodbc.DatabaseError as e:
                    error_code = e.args[0] if e.args else 'UNKNOWN'
                    error_msg = e.args[1] if len(e.args) > 1 else str(e)
                    logger.error(f"Database error executing stored procedure")
                    logger.error(f"Error Code: {error_code}")
                    logger.error(f"Error Message: {error_msg}")
                    logger.error(f"Requirement ID: {requirement_id}, Source ID: {source_id}")
                    if _is_retryable_error(e):
                        raise DatabaseConnectionError(f"Transient database error: {e}") from e
                    raise DatabaseQueryError(f"Database error: {e}") from e
                    
                except pyodbc.Error as e:
                    error_code = e.args[0] if e.args else 'UNKNOWN'
                    error_msg = e.args[1] if len(e.args) > 1 else str(e)
                    logger.error(f"PyODBC error executing stored procedure")
                    logger.error(f"Error Code: {error_code}")
                    logger.error(f"Error Message: {error_msg}")
                    logger.error(f"Full exception: {repr(e)}")
                    logger.error(f"Requirement ID: {requirement_id}, Source ID: {source_id}")
                    if _is_retryable_error(e):
                        raise DatabaseConnectionError(f"Transient database error: {e}") from e
                    raise DatabaseQueryError(f"Database error: {e}") from e
                    
                except Exception as e:
                    logger.error(f"Unexpected error executing stored procedure: {e}", exc_info=True)
                    logger.error(f"Exception type: {type(e).__name__}")
                    logger.error(f"Requirement ID: {requirement_id}, Source ID: {source_id}")
                    raise DatabaseQueryError(f"Unexpected error: {e}") from e
                
                finally:
                    # Ensure cursor is always closed
                    if cursor is not None:
                        try:
                            cursor.close()
                            logger.debug("Cursor closed successfully")
                        except Exception as e:
                            logger.warning(f"Error closing cursor: {e}")
            
            result = await loop.run_in_executor(None, _execute)
            return result
        
        finally:
            # Return connection to pool
            await db_pool.return_connection(conn)
    
    try:
        result = await _execute_with_retry()
        if result is None:
            return None
        mapped_result = _map_details_result_keys(result)
        return mapped_result
        
    except RetryError as e:
        logger.error(f"All retry attempts exhausted for requirement_id={requirement_id}, source_id={source_id}: {e}")
        raise DatabaseConnectionError(
            f"Failed to execute stored procedure after {settings.recommendations_db_retry_attempts} attempts: {e}"
        ) from e
    except (DatabaseConnectionError, DatabaseQueryError) as e:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in execute_details_stored_procedure: {e}", exc_info=True)
        raise DatabaseQueryError(f"Unexpected error: {e}") from e


async def get_recommendations_list(
    candidate_id: int,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Get job recommendations list (summary) for a candidate with optional caching.
    
    This is the main function to retrieve job recommendations list. It handles
    caching, executes the stored procedure, and returns formatted results.
    """
    # Check cache if enabled
    if use_cache:
        from app.services.recommendations.cache_manager import get_cache_manager
        cache = get_cache_manager()
        cached_result = cache.get_list(candidate_id)
        
        if cached_result is not None:
            logger.info(f"Returning cached list results for candidate_id={candidate_id}")
            return cached_result
    
    # Execute stored procedure
    recommendations, total_count = await execute_list_stored_procedure(candidate_id=candidate_id)
    
    # Build response
    response = {
        "candidate_id": candidate_id,
        "recommendations": recommendations,
        "total_count": total_count
    }
    
    # Cache the result if caching is enabled
    if use_cache:
        from app.services.recommendations.cache_manager import get_cache_manager
        cache = get_cache_manager()
        cache.set_list(candidate_id, response)
    
    return response


async def get_recommendation_details(
    requirement_id: int,
    source_id: int,
    use_cache: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Get detailed job information with optional caching.
    
    This function retrieves detailed job information for a specific requirement.
    Returns None if no result found (empty result).
    """
    # Check cache if enabled
    if use_cache:
        from app.services.recommendations.cache_manager import get_cache_manager
        cache = get_cache_manager()
        cached_result = cache.get_details(requirement_id, source_id)
        
        if cached_result is not None:
            logger.info(f"Returning cached details for requirement_id={requirement_id}, source_id={source_id}")
            return cached_result
    
    # Execute stored procedure
    details = await execute_details_stored_procedure(
        requirement_id=requirement_id,
        source_id=source_id
    )
    
    # If no result, return None (empty result)
    if details is None:
        return None
    
    # Add requirement_id and source_id to response for clarity
    details["requirement_id"] = requirement_id
    details["source_id"] = source_id
    
    # Cache the result if caching is enabled
    if use_cache:
        from app.services.recommendations.cache_manager import get_cache_manager
        cache = get_cache_manager()
        cache.set_details(requirement_id, source_id, details)
    
    return details
