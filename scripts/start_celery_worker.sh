#!/bin/bash
# Start Celery worker for webhook processing
#
# Usage:
#   ./scripts/start_celery_worker.sh
#
# Options:
#   --concurrency N    Number of concurrent workers (default: 10)
#   --loglevel LEVEL   Log level (default: info)

CONCURRENCY=${1:-10}
LOGLEVEL=${2:-info}

echo "Starting Celery worker..."
echo "Concurrency: $CONCURRENCY"
echo "Log Level: $LOGLEVEL"

celery -A app.celery_app worker \
    --loglevel=$LOGLEVEL \
    --concurrency=$CONCURRENCY \
    --pool=prefork \
    --max-tasks-per-child=1000 \
    --time-limit=300 \
    --soft-time-limit=240
