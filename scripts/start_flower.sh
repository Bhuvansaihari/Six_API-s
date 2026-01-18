#!/bin/bash
# Start Flower monitoring UI for Celery
#
# Usage:
#   ./scripts/start_flower.sh
#
# Access Flower at: http://localhost:5555

PORT=${1:-5555}

echo "Starting Flower monitoring UI..."
echo "Access at: http://localhost:$PORT"

celery -A app.celery_app flower --port=$PORT
