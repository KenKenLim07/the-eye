param(
  [string]$BackendUrl = $(if ($env:BACKEND_URL) { $env:BACKEND_URL } else { "http://localhost:8000" }),
  [string]$Source = "inquirer",
  [int]$PollSeconds = 5,
  [int]$MaxMinutes = 20
)

$ErrorActionPreference = "Stop"

function Assert-Ok($name, $scriptBlock) {
  Write-Host ("[PIPELINE] " + $name)
  $res = & $scriptBlock
  if ($null -eq $res) { throw ("Pipeline check failed: " + $name + " (null response)") }
  Write-Host ("[OK] " + $name)
  return $res
}

Assert-Ok "GET /health" { Invoke-RestMethod -Uri "$BackendUrl/health" -Method Get -TimeoutSec 30 } | Out-Null

$payload = @{ source = $Source } | ConvertTo-Json
$run = Assert-Ok "POST /scrape/run (source=$Source)" {
  Invoke-RestMethod -Uri "$BackendUrl/scrape/run" -Method Post -ContentType "application/json" -Body $payload -TimeoutSec 30
}

if (-not $run.jobs -or $run.jobs.Count -lt 1) {
  throw "Expected at least one job in /scrape/run response"
}

$taskId = $run.jobs[0].task_id
Write-Host ("[INFO] task_id=" + $taskId)

$deadline = (Get-Date).AddMinutes($MaxMinutes)
while ($true) {
  if ((Get-Date) -gt $deadline) { throw "Timed out waiting for scrape task to finish ($MaxMinutes min)" }

  $st = Invoke-RestMethod -Uri "$BackendUrl/scrape/status/$taskId" -Method Get -TimeoutSec 30
  if ($st.status -eq "completed") { break }
  if ($st.status -eq "failed") { throw ("Scrape task failed: " + ($st.error | Out-String)) }
  Start-Sleep -Seconds $PollSeconds
}

Assert-Ok "GET /articles/home-optimized" {
  Invoke-RestMethod -Uri "$BackendUrl/articles/home-optimized?limit_per_source=2&refresh=true" -Method Get -TimeoutSec 60
} | Out-Null

# These are heavier endpoints on cold cache.
Assert-Ok "GET /ml/trends" {
  Invoke-RestMethod -Uri "$BackendUrl/ml/trends?period=7d&include_today=true&refresh=true" -Method Get -TimeoutSec 180
} | Out-Null

Assert-Ok "GET /ml/entities/top" {
  Invoke-RestMethod -Uri "$BackendUrl/ml/entities/top?period=7d&include_today=true&refresh=true" -Method Get -TimeoutSec 180
} | Out-Null

Write-Host "[DONE] pipeline checks passed"

