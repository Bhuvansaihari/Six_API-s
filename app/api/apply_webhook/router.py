"""
Webhook router for Supabase events

This module handles incoming webhooks from Supabase and enqueues them
for background processing using Celery.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import logging
from app.api.apply_webhook.models import WebhookPayload
from app.tasks.webhook_tasks import process_webhook_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/cand-job-matching")
async def webhook_listener(payload: WebhookPayload, request: Request):
    """
    Webhook endpoint to receive Supabase events and enqueue for processing
    
    This endpoint:
    1. Receives webhook events from Supabase
    2. Validates the payload structure
    3. Enqueues the webhook to Celery for background processing
    4. Returns 202 Accepted immediately (< 50ms response time)
    
    The actual processing happens asynchronously in a Celery worker:
    - Validates event type (INSERT on cand_job_matching table)
    - Checks similarity_score >= 0.7
    - Checks daily application limits
    - Applies filters (remote preference, pay rate)
    - Executes SQL Server stored procedure
    - Creates tracking record in Supabase
    
    Returns:
        202 Accepted: Webhook queued successfully
        500 Internal Server Error: Failed to queue webhook
    """
    try:
        # Extract basic info for logging
        record = payload.record
        cand_id = record.cand_id if record else None
        requirement_id = record.requirement_id if record else None
        
        logger.info(
            f"Received webhook for cand_id={cand_id}, requirement_id={requirement_id}",
            extra={
                'log_to_db': True,
                'service_name': 'webhook_listener',
                'cand_id': cand_id,
                'requirement_id': requirement_id
            }
        )
        
        # Enqueue task to Celery (async, non-blocking)
        task = process_webhook_task.delay(payload.dict())
        
        logger.info(
            f"Webhook queued successfully: task_id={task.id}",
            extra={
                'log_to_db': True,
                'service_name': 'webhook_listener',
                'task_id': task.id,
                'cand_id': cand_id,
                'requirement_id': requirement_id
            }
        )
        
        return JSONResponse(
            status_code=202,  # Accepted
            content={
                "status": "accepted",
                "message": "Webhook queued for processing",
                "task_id": task.id,
                "cand_id": cand_id,
                "requirement_id": requirement_id
            }
        )
        
    except Exception as e:
        logger.error(
            f"Error enqueueing webhook: {str(e)}",
            exc_info=True,
            extra={
                'log_to_db': True,
                'service_name': 'webhook_listener',
                'error': str(e)
            }
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue webhook: {str(e)}"
        )


@router.get("/health")
async def webhook_health():
    """Health check endpoint for webhook service"""
    return {
        "status": "healthy",
        "service": "webhook-listener",
        "mode": "async-celery"
    }
