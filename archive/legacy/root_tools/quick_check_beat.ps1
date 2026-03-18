# Quick Beat Status Checker (ASCII-safe)

Write-Host ""
Write-Host "Celery Beat Quick Status" -ForegroundColor Cyan
Write-Host ("=" * 70)

Write-Host ""
Write-Host "Container Status:" -ForegroundColor Yellow
$beatStatus = docker ps --filter "name=ph-eye-beat" --format "{{.Status}}" 2>$null
$workerStatus = docker ps --filter "name=ph-eye-worker" --format "{{.Status}}" 2>$null

if ($beatStatus) {
    Write-Host "  OK   Beat:   $beatStatus" -ForegroundColor Green
} else {
    Write-Host "  FAIL Beat:   Not running" -ForegroundColor Red
}

if ($workerStatus) {
    Write-Host "  OK   Worker: $workerStatus" -ForegroundColor Green
} else {
    Write-Host "  FAIL Worker: Not running" -ForegroundColor Red
}

Write-Host ""
Write-Host "Redis Queue:" -ForegroundColor Yellow
$queueLength = docker exec ph-eye-redis redis-cli LLEN celery 2>$null
if ($queueLength -ne $null) {
    Write-Host "  Queue length: $queueLength"
} else {
    Write-Host "  Could not query Redis queue" -ForegroundColor Red
}

Write-Host ""
Write-Host "Recent Beat Logs:" -ForegroundColor Yellow
docker logs --tail 20 ph-eye-beat 2>&1

Write-Host ""
Write-Host "Recent Worker Task Events:" -ForegroundColor Yellow
docker logs --tail 120 ph-eye-worker 2>&1 | Select-String -Pattern "received|succeeded|retry|failed" | Select-Object -Last 20

Write-Host ""
Write-Host "Commands:" -ForegroundColor Cyan
Write-Host "  Watch beat:   docker logs -f ph-eye-beat"
Write-Host "  Watch worker: docker logs -f ph-eye-worker"
Write-Host "  Next runs:    docker exec ph-eye-beat python /app/check_next_runs.py"
Write-Host "  Queue len:    docker exec ph-eye-redis redis-cli LLEN celery"
Write-Host ""
