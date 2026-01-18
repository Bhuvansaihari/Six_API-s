"""
Celery application for background task processing

This module configures Celery for handling webhook processing asynchronously.
Tasks are queued to Redis and processed by background workers.
"""
from celery import Celery
from config import get_settings

settings = get_settings()

# Initialize Celery app
celery_app = Celery(
    'autoapply_tasks',
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=['app.tasks.webhook_tasks']  # Auto-discover tasks
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    result_expires=3600,  # Results expire after 1 hour
    
    # Timezone
    timezone='UTC',
    enable_utc=True,
    
    # Task execution
    task_acks_late=True,  # Acknowledge after task completion (ensures retry on worker crash)
    task_reject_on_worker_lost=True,  # Requeue if worker dies mid-task
    worker_prefetch_multiplier=1,  # Fetch one task at a time (fair distribution)
    
    # Timeouts
    task_time_limit=300,  # Hard limit: 5 minutes
    task_soft_time_limit=240,  # Soft limit: 4 minutes (raises exception)
    
    # Retry policy
    task_default_retry_delay=60,  # Default retry delay: 1 minute
    task_max_retries=3,  # Default max retries
    
    # Result backend
    result_backend_transport_options={
        'master_name': 'mymaster',
        'visibility_timeout': 3600,
    },
    
    # Logging
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
)

# Optional: Configure task routes (for multiple queues)
celery_app.conf.task_routes = {
    'app.tasks.webhook_tasks.process_webhook_task': {'queue': 'webhooks'},
}
