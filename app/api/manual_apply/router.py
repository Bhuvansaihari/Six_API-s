"""
FastAPI router for Manual Apply API.
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
import logging
from app.api.manual_apply.schemas import ManualApplyRequest, ManualApplyResponse
from app.api.manual_apply.logic import ManualApplyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/apply-job", tags=["manual-apply"])


def get_manual_apply_service(request: Request) -> ManualApplyService:
    """Get or create manual apply service (lazy initialization)"""
    if not hasattr(request.app.state, 'manual_apply_service'):
        request.app.state.manual_apply_service = ManualApplyService()
    return request.app.state.manual_apply_service


@router.post("", response_model=ManualApplyResponse, status_code=200)
async def apply_job(
    request_body: ManualApplyRequest,
    request: Request,
    service: ManualApplyService = Depends(get_manual_apply_service)
):
    """
    Manually apply a candidate to a job requirement
    
    This endpoint:
    1. Accepts candidate_id and requirement_id
    2. Fetches candidate data from auto_apply_cand table
    3. Executes Usp_SC_JobSeeker_IU_ApplyJob stored procedure
    4. Creates tracking record in job_application_tracking (with NULL matching_id and similarity_score)
    
    **Note:** This is a manual application, so it does not require a similarity score or matching_id.
    The tracking record will have NULL values for matching_id and similarity_score.
    """
    try:
        logger.info(f"Received manual apply request: cand_id={request_body.cand_id}, requirement_id={request_body.requirement_id}")
        
        # Process application
        result = await service.apply_candidate_to_job(
            request_body.cand_id,
            request_body.requirement_id
        )
        
        # Return appropriate HTTP status based on result
        if result.get("success"):
            return JSONResponse(
                status_code=200,
                content=result
            )
        else:
            # Return 400 for validation errors, 500 for other errors
            status_code = 400 if "not found" in result.get("message", "").lower() else 500
            raise HTTPException(
                status_code=status_code,
                detail=result.get("message", "Failed to process application")
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling manual apply request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

