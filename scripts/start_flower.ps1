# Start Flower monitoring UI for Celery
#
# Usage:
#   .\scripts\start_flower.ps1
#   .\scripts\start_flower.ps1 -Port 8080

param(
    [int]$Port = 5555
)

Write-Host "Starting Flower monitoring UI..." -ForegroundColor Green
Write-Host "Access at: http://localhost:$Port" -ForegroundColor Cyan

celery -A app.celery_app flower --port=$Port
