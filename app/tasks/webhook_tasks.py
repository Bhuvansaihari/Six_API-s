"""
Background tasks for webhook processing

This module contains Celery tasks for asynchronous webhook processing.
"""
from app.celery_app import celery_app
from app.api.apply_webhook.logic import WebhookProcessingService
import logging
import asyncio

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name='process_webhook_task',
    max_retries=3,
    default_retry_delay=60,  # Retry after 1 minute
    autoretry_for=(Exception,),  # Auto-retry on any exception
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=600,  # Max 10 minutes between retries
    retry_jitter=True  # Add randomness to prevent thundering herd
)
def process_webhook_task(self, webhook_data: dict):
    """
    Background task to process webhook from Supabase
    
    This task:
    1. Validates the webhook payload
    2. Checks similarity score threshold
    3. Fetches candidate data
    4. Applies filters (remote preference, pay rate)
    5. Executes SQL Server stored procedure
    6. Creates tracking record
    
    Args:
        webhook_data: Webhook payload from Supabase
        
    Returns:
        dict: Processing result with success status and details
    """
    try:
        logger.info(
            f"Processing webhook task {self.request.id} for "
            f"cand_id={webhook_data.get('record', {}).get('cand_id')}, "
            f"requirement_id={webhook_data.get('record', {}).get('requirement_id')}"
        )
        
        # Initialize service
        service = WebhookProcessingService()
        
        # Process webhook (run async function in sync context)
        result = asyncio.run(service.process_webhook(webhook_data))
        
        # Log result
        if result.get('success'):
            logger.info(
                f"Webhook task {self.request.id} completed successfully: "
                f"application_id={result.get('application_id')}",
                extra={
                    'log_to_db': True,
                    'service_name': 'webhook_task',
                    'task_id': self.request.id,
                    'cand_id': webhook_data.get('record', {}).get('cand_id'),
                    'requirement_id': webhook_data.get('record', {}).get('requirement_id'),
                    'application_id': result.get('application_id')
                }
            )
        else:
            reason = result.get('reason', 'unknown')
            logger.info(
                f"Webhook task {self.request.id} skipped: {result.get('message')} (reason: {reason})"
            )
        
        return result
        
    except Exception as exc:
        logger.error(
            f"Webhook task {self.request.id} failed: {str(exc)}",
            exc_info=True,
            extra={
                'log_to_db': True,
                'service_name': 'webhook_task',
                'task_id': self.request.id,
                'error': str(exc)
            }
        )
        
        # Retry with exponential backoff
        # Celery will handle this automatically due to autoretry_for
        raise
