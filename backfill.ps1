param(
  [int]$Days = 7,
  [int]$BatchSize = 100,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

Write-Host "Starting ML analysis backfill for last $Days days..."
Write-Host "Batch size: $BatchSize"
if ($DryRun) {
  Write-Host "Dry run: enabled (no tasks will be queued)"
}
Write-Host ""

function Get-ComposeCommand {
  if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
    return @("docker-compose")
  }
  return @("docker", "compose")
}

$compose = Get-ComposeCommand

$cmd = $compose + @(
  "exec", "worker_ml", "python", "/app/scripts/backfill_ml_analysis.py",
  "--days", $Days,
  "--batch-size", $BatchSize
)
if ($DryRun) {
  $cmd += "--dry-run"
}

& $cmd

Write-Host ""
Write-Host "Backfill command completed. Monitor progress with:"
Write-Host "  docker compose logs -f worker_ml"
Write-Host "  # or:"
Write-Host "  docker logs -f ph-eye-worker-ml"
