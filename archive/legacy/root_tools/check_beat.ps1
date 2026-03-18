# PowerShell script to check Celery Beat status on Windows
Write-Host "🔍 Celery Beat Status Check" -ForegroundColor Cyan
Write-Host "=" * 60

# Check if containers are running
Write-Host "`n📦 Docker Container Status:" -ForegroundColor Yellow
Write-Host "-" * 60

$containers = @("ph-eye-beat", "ph-eye-worker", "ph-eye-redis", "ph-eye-api")
foreach ($container in $containers) {
    $status = docker ps --filter "name=$container" --format "{{.Status}}" 2>$null
    if ($status) {
        Write-Host "✅ $container : $status" -ForegroundColor Green
    } else {
        Write-Host "❌ $container : Not running" -ForegroundColor Red
    }
}

# Check beat logs
Write-Host "`n📋 Beat Container Logs (last 20 lines):" -ForegroundColor Yellow
Write-Host "-" * 60
docker logs --tail 20 ph-eye-beat 2>&1

# Check worker logs for task activity
Write-Host "`n⚙️ Worker Container Logs (last 10 lines):" -ForegroundColor Yellow
Write-Host "-" * 60
docker logs --tail 10 ph-eye-worker 2>&1

# Check Redis queue
Write-Host "`n📊 Redis Queue Status:" -ForegroundColor Yellow
Write-Host "-" * 60
$queueLength = docker exec ph-eye-redis redis-cli LLEN celery 2>$null
if ($queueLength -ne $null) {
    Write-Host "   Tasks in queue: $queueLength" -ForegroundColor $(if ([int]$queueLength -gt 0) { "Green" } else { "Yellow" })
} else {
    Write-Host "   ⚠️  Could not check queue (Redis may not be accessible)" -ForegroundColor Red
}

# Check beat schedule file
Write-Host "`n💡 Quick Commands:" -ForegroundColor Cyan
Write-Host "   • Watch beat logs: docker logs -f ph-eye-beat"
Write-Host "   • Watch worker logs: docker logs -f ph-eye-worker"
Write-Host "   • Check queue: docker exec -it ph-eye-redis redis-cli LLEN celery"
Write-Host "   • Restart beat: docker-compose restart beat"
Write-Host ""
