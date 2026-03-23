param(
  [int]$Days = 7,
  [switch]$Apply,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if (-not $Apply -and -not $DryRun) {
  $DryRun = $true
}

function Get-ComposeCommand {
  if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
    return @("docker-compose")
  }
  return @("docker", "compose")
}

$compose = Get-ComposeCommand

$cmd = $compose + @(
  "exec", "worker_ml", "python", "/app/scripts/fix_published_at_drift.py",
  "--days", $Days
)

if ($Apply) {
  $cmd += "--apply"
} else {
  $cmd += "--dry-run"
}

& $cmd

