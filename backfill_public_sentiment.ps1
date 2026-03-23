# Backfill `article_sentiment_public` from `bias_analysis` (PowerShell)
#
# Usage:
#   .\backfill_public_sentiment.ps1 [-Days 7] [-Apply] [-BatchSize 500]
#
param(
  [int]$Days = 7,
  [switch]$Apply,
  [int]$BatchSize = 500
)

$compose = "docker"
$composeArgs = @("compose")

# Support old docker-compose if docker compose isn't available
try {
  docker compose version | Out-Null
} catch {
  $compose = "docker-compose"
  $composeArgs = @()
}

$argsList = @()
$argsList += $composeArgs
$argsList += @(
  "exec",
  "worker_ml",
  "python",
  "/app/scripts/backfill_article_sentiment_public.py",
  "--days", "$Days",
  "--batch-size", "$BatchSize"
)

if ($Apply) {
  $argsList += "--apply"
} else {
  $argsList += "--dry-run"
}

& $compose @argsList

