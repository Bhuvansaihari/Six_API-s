"""FastAPI router for resume processing with caching, rate limiting, and async support."""

import os
import hashlib
import tempfile
import time
import logging
import traceback
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from aiocache import Cache

from app.api.resume_intake.logic import process_resume_async

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resume-intake", tags=["resume-intake"])


def get_cache(request: Request) -> Cache:
    """Get cache from app state."""
    return request.app.state.resume_cache


@router.post("/process-resume")
async def process_resume_endpoint(
    request: Request,
    file: UploadFile = File(...),
    candidate_id: int = Query(..., description="Candidate ID from logged-in user (required)")
):
    """
    Process a resume file and update database records.
    
    Accepts PDF, DOCX, or TXT files and processes them through the pipeline:
    1. Extract text from resume
    2. Structure data using GPT-4o
    3. Update records in Supabase database (auto_apply_cand and parsed_cand_resume)
    4. Generate and store embeddings in Qdrant
    
    Note: Rate limiting is configured at the application level (10 requests per minute per IP).
    
    Args:
        request: FastAPI request object (for caching)
        file: Uploaded resume file (PDF, DOCX, or TXT)
        candidate_id: Candidate ID from logged-in user (required)
        
    Returns:
        JSON response with success status and candidate_id
        
    Raises:
        HTTPException: If file type is unsupported, candidate_id is invalid, or processing fails
    """
    # Validate file type
    allowed_extensions = {'.pdf', '.docx', '.doc', '.txt'}
    file_extension = Path(file.filename).suffix.lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Validate candidate_id
    if candidate_id is None or candidate_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="candidate_id is required. Must be a positive integer."
        )
    
    # Get cache from app state
    cache = get_cache(request)
    
    # Note: Rate limiting infrastructure is initialized in main.py
    # Rate limit: 10 requests per minute per IP (handled at application level)
    
    # Check cache first (using file hash + candidate_id as key)
    content = await file.read()
    file_hash = hashlib.md5(content).hexdigest()
    cache_key = f"resume:{candidate_id}:{file_hash}"
    
    # Try to get from cache
    cached_result = await cache.get(cache_key)
    if cached_result:
        logger.info(f"Cache hit for candidate_id={candidate_id}, file_hash={file_hash[:8]}")
        return JSONResponse(
            status_code=200,
            content={
                **cached_result,
                "cached": True
            }
        )
    
    # Reset file pointer for processing
    await file.seek(0)
    
    # Save uploaded file temporarily
    tmp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
            # Write uploaded file content to temporary file
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
            # File is automatically closed when exiting the 'with' block
        
        # Process the resume (async) - file is now closed, pass candidate_id
        result = await process_resume_async(tmp_file_path, candidate_id=candidate_id)
        
        if result["success"]:
            # Cache the result
            await cache.set(cache_key, result, ttl=3600)  # Cache for 1 hour
            
            logger.info(f"Successfully processed resume for candidate_id={candidate_id}")
            
            return JSONResponse(
                status_code=200,
                content={
                    **result,
                    "cached": False
                }
            )
        else:
            logger.error(f"Resume processing failed for candidate_id={candidate_id}: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Unknown error occurred")
            )
            
    except HTTPException:
        raise
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Error processing resume for candidate_id={candidate_id}: {str(e)}")
        logger.debug(f"Traceback: {error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing resume: {str(e)}"
        )
    finally:
        # Clean up temporary file with error handling for Windows
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                # On Windows, sometimes need to wait a bit for file handles to release
                time.sleep(0.1)  # Small delay to ensure file is released
                os.unlink(tmp_file_path)
            except (PermissionError, OSError) as e:
                # Log but don't fail if we can't delete the temp file
                # It will be cleaned up by the OS eventually
                logger.warning(f"Could not delete temporary file {tmp_file_path}: {e}")


@router.get("/cache/stats")
async def cache_stats(request: Request):
    """
    Get cache statistics for resume processing.
    
    Returns:
        Dictionary with cache configuration information
    """
    return {
        "cache_type": "memory",
        "namespace": "resume_api",
        "timeout": 3600
    }

