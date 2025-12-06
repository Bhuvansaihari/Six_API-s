from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
import logging
from app.api.apply_webhook.models import WebhookPayload
from app.api.apply_webhook.logic import WebhookProcessingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


def get_webhook_service(request: Request) -> WebhookProcessingService:
    """Get or create webhook service (lazy initialization)"""
    if not hasattr(request.app.state, 'webhook_service'):
        request.app.state.webhook_service = WebhookProcessingService()
    return request.app.state.webhook_service


@router.post("/cand-job-matching")
async def webhook_listener(
    payload: WebhookPayload,
    request: Request,
    webhook_service: WebhookProcessingService = Depends(get_webhook_service)
):
    """
    Webhook endpoint to listen for Supabase events on cand_job_matching table
    
    This endpoint:
    1. Receives webhook events from Supabase
    2. Validates the event (INSERT on cand_job_matching table)
    3. Checks if similarity_score >= 0.7
    4. Fetches candidate data from auto_apply_cand table
    5. Executes Usp_SC_JobSeeker_IU_ApplyJob stored procedure
    """
    try:
        logger.info(f"Received webhook payload: {payload.dict()}")
        
        # Convert Pydantic model to dict for processing
        payload_dict = payload.dict()
        
        # Process webhook (async)
        result = await webhook_service.process_webhook(payload_dict)
        
        # Return appropriate HTTP status based on result
        if result.get("success"):
            return JSONResponse(
                status_code=200,
                content=result
            )
        else:
            # Return 200 even for skipped events (similarity < 0.7) to acknowledge receipt
            # But log it appropriately
            if "below threshold" in result.get("message", ""):
                logger.info(f"Webhook processed but skipped: {result.get('message')}")
            else:
                logger.warning(f"Webhook processing failed: {result.get('message')}")
            
            return JSONResponse(
                status_code=200,  # Return 200 to acknowledge receipt, even if processing skipped
                content=result
            )
            
    except Exception as e:
        logger.error(f"Error handling webhook request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

