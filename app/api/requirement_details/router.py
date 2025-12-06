"""
FastAPI router for Requirement Details API.

This module provides the REST API endpoint to retrieve requirement details
by executing the Beta_usp_Get_Requirement_Details stored procedure.
"""

import asyncio
import logging
import time
from typing import Dict, Any
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
import pyodbc

from config import get_settings
from app.api.requirement_details.schemas import RequirementDetailsResponse
from app.services.requirement_details.db_pool import get_db_pool
from app.services.requirement_details.cache import (
    get_cached_requirement,
    set_cached_requirement
)

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/requirement", tags=["requirement-details"])


def get_limiter(request: Request) -> Limiter:
    """Get rate limiter from app state."""
    return request.app.state.requirement_details_limiter


async def run_in_executor(func, *args):
    """
    Run a blocking function in executor.
    
    Args:
        func: The blocking function to run
        *args: Arguments to pass to the function
        
    Returns:
        The result of the function execution
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


def execute_stored_procedure(
    conn: pyodbc.Connection,
    requirement_id: int,
    company_id: int = 1
) -> Dict[str, Any]:
    """
    Execute the stored procedure and extract required columns.
    
    This runs in a thread pool since pyodbc is blocking.
    
    Args:
        conn (pyodbc.Connection): Database connection
        requirement_id (int): The requirement ID to fetch
        company_id (int): Company ID (default: 1)
        
    Returns:
        Dict[str, Any]: Mapped result with user-friendly keys, or None if not found
        
    Raises:
        Exception: If database error occurs
    """
    cursor = conn.cursor()
    
    try:
        # Execute the stored procedure
        cursor.execute(
            "EXEC [dbo].[Beta_usp_Get_Requirement_Details] @CompanyID=?, @RequirementID=?",
            company_id,
            requirement_id
        )
        
        # Fetch the first result set (main requirement details)
        row = cursor.fetchone()
        
        if not row:
            return None
        
        # Get column names
        columns = [column[0] for column in cursor.description]
        
        # Create a dictionary from the row
        result = dict(zip(columns, row))
        
        # Extract only the required columns and map to user-friendly keys
        mapped_result = {
            "JobTitle": result.get("JobTitleText"),
            "City": result.get("CityName"),
            "ZIPCode": result.get("ZIPCode"),
            "Duration": result.get("RequirementDuration"),
            "ShiftTimingFrom": result.get("RequirementShiftTimingFrom"),
            "ShiftTimingTo": result.get("RequirementShiftTimingTo"),
            "HoursPerWeek": result.get("RequirementHoursPerWeek"),
            "MinPayRate": result.get("MinPayRate"),
            "MaxPayRate": result.get("MaxPayRate"),
            "JobDescription": result.get("RequirementJobDescription")
        }
        
        # Move to next result set if exists (for shift timings)
        while cursor.nextset():
            pass
        
        return mapped_result
        
    except pyodbc.Error as e:
        logger.error(f"Database error executing stored procedure: {e}")
        raise Exception(f"Database error: {str(e)}")
    finally:
        cursor.close()


@router.get("/{requirement_id}", response_model=RequirementDetailsResponse)
async def get_requirement_details(
    request: Request,
    requirement_id: int,
    company_id: int = Query(1, description="Company ID (default: 1)", gt=0)
):
    """
    Get requirement details by ID.
    
    This endpoint executes the Beta_usp_Get_Requirement_Details stored procedure
    with the provided requirement_id and company_id, and returns requirement
    details with user-friendly field names.
    
    Rate limiting is applied via the limiter from app state.
    
    Args:
        request: FastAPI request object (for rate limiting)
        requirement_id: The requirement ID to fetch (required, must be > 0)
        company_id: Company ID (default: 1, must be > 0)
        
    Returns:
        RequirementDetailsResponse: Requirement details with mapped field names
        
    Raises:
        HTTPException:
            - 404: If requirement is not found
            - 500: If database operation fails
    """
    """
    Get requirement details by ID.
    
    This endpoint executes the Beta_usp_Get_Requirement_Details stored procedure
    with the provided requirement_id and company_id, and returns requirement
    details with user-friendly field names.
    
    Args:
        request: FastAPI request object (for rate limiting)
        requirement_id: The requirement ID to fetch (required, must be > 0)
        company_id: Company ID (default: 1, must be > 0)
        
    Returns:
        RequirementDetailsResponse: Requirement details with mapped field names
        
    Raises:
        HTTPException:
            - 404: If requirement is not found
            - 500: If database operation fails
    """
    start_time = time.time()
    settings = get_settings()
    logger.info(
        f"Request for requirement_id={requirement_id}, company_id={company_id} "
        f"from {get_remote_address(request)}"
    )
    
    try:
        # Check cache first
        cached_data = await get_cached_requirement(requirement_id)
        if cached_data:
            elapsed = time.time() - start_time
            logger.info(
                f"Cache hit for requirement_id={requirement_id} (took {elapsed:.3f}s)"
            )
            return RequirementDetailsResponse(**cached_data)
        
        logger.debug(
            f"Cache miss for requirement_id={requirement_id}, querying database"
        )
        
        # Get database connection from pool
        pool = await get_db_pool()
        
        async with pool.get_connection_context() as conn:
            # Execute stored procedure in executor (since pyodbc is blocking)
            result = await run_in_executor(
                execute_stored_procedure,
                conn,
                requirement_id,
                company_id
            )
            
            if result is None:
                elapsed = time.time() - start_time
                logger.warning(
                    f"Requirement not found: requirement_id={requirement_id} "
                    f"(took {elapsed:.3f}s)"
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Requirement with ID {requirement_id} not found"
                )
            
            # Cache the result
            await set_cached_requirement(requirement_id, result, ttl=300)
            
            elapsed = time.time() - start_time
            logger.info(
                f"Successfully fetched requirement_id={requirement_id} from database "
                f"(took {elapsed:.3f}s)"
            )
            
            return RequirementDetailsResponse(**result)
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(
            f"Error fetching requirement_id={requirement_id}: {str(e)} "
            f"(took {elapsed:.3f}s)",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching requirement details: {str(e)}"
        )

