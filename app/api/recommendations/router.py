"""
FastAPI router for Get Recommendations API.

This module provides the REST API endpoint to retrieve job recommendations
for candidates by executing the USP_SC_Get_JobSeekerRecommenededJobList stored procedure.
"""

from fastapi import APIRouter, HTTPException, Query, status, Request
from fastapi.responses import JSONResponse
from typing import Optional
import logging
import asyncio

from app.services.recommendations.database_service import (
    get_recommendations,
    DatabaseConnectionError,
    DatabaseQueryError,
    DatabaseTimeoutError
)
from app.services.recommendations.cache_manager import get_cache_manager
from config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("")
async def get_job_recommendations(
    request: Request,
    candidate_id: int = Query(..., description="The candidate ID to get recommendations for", gt=0),
    use_cache: Optional[bool] = Query(True, description="Whether to use cache for this request")
) -> JSONResponse:
    """
    Get job recommendations for a candidate.
    
    This endpoint executes the USP_SC_Get_JobSeekerRecommenededJobList stored procedure
    with the provided candidate_id and returns job recommendations in JSON format.
    
    The stored procedure is called with the following constant parameters:
    - PageNo: 1
    - PageSize: 10
    - JobActivityTypeID: 0
    
    Args:
        request: FastAPI request object (for rate limiting)
        candidate_id: The candidate ID (required, must be > 0)
        use_cache: Whether to use cache. Defaults to True.
        
    Returns:
        JSONResponse: JSON response containing:
            - candidate_id: The candidate ID
            - recommendations: List of job recommendations with clean key names
            - total_count: Total number of recommendations available
            - page_no: Current page number (always 1)
            - page_size: Page size (always 10)
            
    Raises:
        HTTPException: 
            - 400: If candidate_id is invalid
            - 500: If database operation fails
            - 503: If service is unavailable
            - 504: If request times out
    """
    try:
        settings = get_settings()
        logger.info(f"Received request for candidate_id={candidate_id}, use_cache={use_cache}")
        
        # Note: Rate limiting is handled at the application level via limiter middleware
        
        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                get_recommendations(
                    candidate_id=candidate_id,
                    use_cache=use_cache
                ),
                timeout=settings.recommendations_request_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Request timeout for candidate_id={candidate_id} after {settings.recommendations_request_timeout}s")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Request timed out after {settings.recommendations_request_timeout} seconds"
            )
        
        logger.info(
            f"Successfully retrieved {len(result.get('recommendations', []))} "
            f"recommendations for candidate_id={candidate_id}"
        )
        
        return JSONResponse(
            content=result,
            status_code=status.HTTP_200_OK
        )
        
    except ValueError as e:
        logger.warning(f"Invalid request parameter: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except DatabaseConnectionError as e:
        logger.error(f"Database connection error for candidate_id={candidate_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service temporarily unavailable. Please try again later."
        )
    except DatabaseQueryError as e:
        logger.error(f"Database query error for candidate_id={candidate_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request."
        )
    except DatabaseTimeoutError as e:
        logger.error(f"Database timeout for candidate_id={candidate_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Database operation timed out. Please try again later."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error retrieving recommendations for candidate_id={candidate_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later."
        )


@router.get("/cache/stats")
async def get_cache_stats():
    """
    Get cache statistics.
    
    Returns:
        Dict[str, Any]: Cache statistics including entry counts and TTL
    """
    cache = get_cache_manager()
    return cache.get_stats()


@router.delete("/cache/clear")
async def clear_cache():
    """
    Clear all cached entries.
    
    Returns:
        Dict[str, str]: Confirmation message
    """
    cache = get_cache_manager()
    cache.clear()
    return {"message": "Cache cleared successfully"}

