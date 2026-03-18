# Watch tasks fire in real-time
Write-Host "🔍 Watching Celery Beat - Tasks should fire every 1-2 minutes" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# Watch beat logs for task scheduling
docker logs -f ph-eye-beat
