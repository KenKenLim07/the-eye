param(
  [int]$Days = 7,
  [int]$BatchSize = 100
)

$ErrorActionPreference = "Stop"

Write-Host "Starting ML analysis backfill for last $Days days..."
Write-Host "Batch size: $BatchSize"
Write-Host ""

function Get-ComposeCommand {
  if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
    return @("docker-compose")
  }
  return @("docker", "compose")
}

$compose = Get-ComposeCommand

& $compose exec api python /app/scripts/backfill_ml_analysis.py --days $Days --batch-size $BatchSize

Write-Host ""
Write-Host "Backfill command completed. Monitor progress with:"
Write-Host "  docker compose logs -f worker"
