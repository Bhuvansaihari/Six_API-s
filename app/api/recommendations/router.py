"""
FastAPI router for Get Recommendations API.

This module provides REST API endpoints to retrieve job recommendations
for candidates by executing stored procedures.
"""

from fastapi import APIRouter, HTTPException, Query, Path, status, Request
from fastapi.responses import JSONResponse
from typing import Optional
import logging
import asyncio

from app.services.recommendations.database_service import (
    get_recommendations_list,
    get_recommendation_details,
    DatabaseConnectionError,
    DatabaseQueryError,
    DatabaseTimeoutError
)
from app.services.recommendations.cache_manager import get_cache_manager
from config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("")
async def get_job_recommendations_list(
    request: Request,
    candidate_id: int = Query(..., description="The candidate ID to get recommendations for", gt=0),
    use_cache: Optional[bool] = Query(True, description="Whether to use cache for this request")
) -> JSONResponse:
    """
    Get job recommendations list (summary) for a candidate.
    
    This endpoint executes the USP_AI_Get_JobSeekerRecommenededJobList stored procedure
    with the provided candidate_id and returns a summary list of job recommendations.
    
    Args:
        request: FastAPI request object (for rate limiting)
        candidate_id: The candidate ID (required, must be > 0)
        use_cache: Whether to use cache. Defaults to True.
        
    Returns:
        JSONResponse: JSON response containing:
            - candidate_id: The candidate ID
            - recommendations: List of job recommendations with requirement_id, job_title, location, source_id
            - total_count: Total number of recommendations available
            
    Raises:
        HTTPException: 
            - 400: If candidate_id is invalid
            - 500: If database operation fails
            - 503: If service is unavailable
            - 504: If request times out
    """
    try:
        settings = get_settings()
        logger.info(f"Received list request for candidate_id={candidate_id}, use_cache={use_cache}")
        
        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                get_recommendations_list(
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
            f"Unexpected error retrieving recommendations list for candidate_id={candidate_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later."
        )


@router.get("/{requirement_id}")
async def get_job_recommendation_details(
    request: Request,
    requirement_id: int = Path(..., description="The requirement ID to get details for", gt=0),
    source_id: int = Query(..., description="The source ID (1 for TA/RequirementMaster, 2 for DE/JobCollection)", gt=0),
    use_cache: Optional[bool] = Query(True, description="Whether to use cache for this request")
) -> JSONResponse:
    """
    Get detailed job information for a specific requirement.
    
    This endpoint executes the USP_AI_Get_JobSeekerRecommenededJobDetails stored procedure
    with the provided requirement_id and source_id and returns detailed job information.
    
    Args:
        request: FastAPI request object (for rate limiting)
        requirement_id: The requirement ID (required, must be > 0)
        source_id: The source ID - 1 for TA/RequirementMaster, 2 for DE/JobCollection (required, must be 1 or 2)
        use_cache: Whether to use cache. Defaults to True.
        
    Returns:
        JSONResponse: JSON response containing detailed job information, or empty result if not found.
            
    Raises:
        HTTPException: 
            - 400: If requirement_id or source_id is invalid
            - 500: If database operation fails
            - 503: If service is unavailable
            - 504: If request times out
    """
    try:
        # Validate source_id
        if source_id not in [1, 2]:
            raise ValueError("source_id must be 1 (TA) or 2 (DE)")
        
        settings = get_settings()
        logger.info(f"Received details request for requirement_id={requirement_id}, source_id={source_id}, use_cache={use_cache}")
        
        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                get_recommendation_details(
                    requirement_id=requirement_id,
                    source_id=source_id,
                    use_cache=use_cache
                ),
                timeout=settings.recommendations_request_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Request timeout for requirement_id={requirement_id}, source_id={source_id} after {settings.recommendations_request_timeout}s")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Request timed out after {settings.recommendations_request_timeout} seconds"
            )
        
        # If no result found, return empty result (as per requirement)
        if result is None:
            logger.info(f"No details found for requirement_id={requirement_id}, source_id={source_id}")
            return JSONResponse(
                content={},
                status_code=status.HTTP_200_OK
            )
        
        logger.info(f"Successfully retrieved details for requirement_id={requirement_id}, source_id={source_id}")
        
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
        logger.error(f"Database connection error for requirement_id={requirement_id}, source_id={source_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service temporarily unavailable. Please try again later."
        )
    except DatabaseQueryError as e:
        logger.error(f"Database query error for requirement_id={requirement_id}, source_id={source_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request."
        )
    except DatabaseTimeoutError as e:
        logger.error(f"Database timeout for requirement_id={requirement_id}, source_id={source_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Database operation timed out. Please try again later."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error retrieving recommendation details for requirement_id={requirement_id}, source_id={source_id}: {e}",
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
