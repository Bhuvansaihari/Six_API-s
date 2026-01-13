"""
Router module for Browse Job List API.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

# Import from the new service
from app.services.job_list.database_service import (
    execute_job_list_stored_procedure,
    DatabaseConnectionError,
    DatabaseQueryError
)
# Import cache manager
from app.services.job_list.cache_manager import get_cache_manager

# Configure logging
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(
    prefix="/job-list",
    tags=["Browse Job List"]
)


@router.get(
    "/",
    summary="Get Job List",
    description="Retrieve a list of jobs for a candidate from SQL Server using USP_AI_Get_JobList",
    response_model=Dict[str, Any]
)
@limiter.limit("10/minute")
async def get_job_list(
    request: Request,
    candidate_id: int = Query(..., description="Candidate ID (required)"),
    use_cache: bool = Query(True, description="Whether to use cached results")
):
    """
    Get job list for a candidate.
    
    Args:
        request: FastAPI request object (for rate limiting)
        candidate_id: The candidate ID to get jobs for
        use_cache: Whether to use caching (default: True)
        
    Returns:
        JSON response with job list and total count
    """
    try:
        logger.info(f"Received request for job list: candidate_id={candidate_id}")
        
        # Check cache if enabled
        if use_cache:
            cache_manager = get_cache_manager()
            cached_result = cache_manager.get_list(candidate_id=candidate_id)
            if cached_result:
                logger.info(f"Returning cached job list for candidate_id={candidate_id}")
                return cached_result

        # Execute stored procedure
        job_list, total_count = await execute_job_list_stored_procedure(candidate_id=candidate_id)
        
        # Build response
        response = {
            "candidate_id": candidate_id,
            "job_list": job_list,
            "total_count": total_count
        }
        
        # Cache the result if caching is enabled
        if use_cache:
            cache_manager = get_cache_manager()
            cache_manager.set_list(candidate_id=candidate_id, value=response)
        
        return response
        
    except ValueError as e:
        logger.warning(f"Validation error in get_job_list: {e}")
        raise HTTPException(status_code=400, detail=str(e))
        
    except DatabaseConnectionError as e:
        logger.error(f"Database connection error in get_job_list: {e}")
        raise HTTPException(status_code=503, detail="Database connection failed")
        
    except DatabaseQueryError as e:
        logger.error(f"Database query error in get_job_list: {e}")
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")
        
    except Exception as e:
        logger.error(f"Unexpected error in get_job_list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics."""
    cache = get_cache_manager()
    return cache.get_stats()


@router.delete("/cache/clear")
async def clear_cache():
    """Clear all cached entries."""
    cache = get_cache_manager()
    cache.clear()
    return {"message": "Cache cleared successfully"}
