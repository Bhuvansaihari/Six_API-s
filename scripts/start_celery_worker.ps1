# Start Celery worker for webhook processing
#
# Usage:
#   .\scripts\start_celery_worker.ps1
#   .\scripts\start_celery_worker.ps1 -Concurrency 20 -LogLevel debug

param(
    [int]$Concurrency = 10,
    [string]$LogLevel = "info"
)

Write-Host "Starting Celery worker..." -ForegroundColor Green
Write-Host "Concurrency: $Concurrency" -ForegroundColor Cyan
Write-Host "Log Level: $LogLevel" -ForegroundColor Cyan

celery -A app.celery_app worker `
    --loglevel=$LogLevel `
    --concurrency=$Concurrency `
    --pool=solo `
    --max-tasks-per-child=1000 `
    --time-limit=300 `
    --soft-time-limit=240
