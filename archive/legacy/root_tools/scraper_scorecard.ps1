$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "Scraper Reliability Scorecard"
Write-Host "======================================================================"
Write-Host ""

Write-Host "1) Last 24h run status from scraping_logs"
Write-Host "----------------------------------------------------------------------"
@'
from app.core.supabase import get_supabase
from datetime import datetime, timedelta, timezone
from collections import defaultdict

sb = get_supabase()
start = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
res = sb.table("scraping_logs").select("source,status,articles_scraped,error_message,started_at").gte("started_at", start).order("started_at", desc=False).execute()
rows = res.data or []
print(f"rows={len(rows)}")
by = defaultdict(lambda: {"total":0, "success":0, "error":0, "failure":0, "articles":0, "with_error_message":0})
for r in rows:
    source = (r.get("source") or "unknown").lower()
    status = (r.get("status") or "").lower()
    b = by[source]
    b["total"] += 1
    if status in b:
        b[status] += 1
    b["articles"] += int(r.get("articles_scraped") or 0)
    if r.get("error_message"):
        b["with_error_message"] += 1

for source in sorted(by):
    b = by[source]
    success_rate = (b["success"] / b["total"] * 100) if b["total"] else 0
    avg_articles = (b["articles"] / b["total"]) if b["total"] else 0
    print(f"{source:15s} total={b['total']:2d} success={b['success']:2d} error={b['error']:2d} failure={b['failure']:2d} success_rate={success_rate:5.1f}% avg_articles={avg_articles:5.2f} err_msgs={b['with_error_message']}")

print("")
print("Recent errors/failures:")
for r in rows:
    st = (r.get("status") or "").lower()
    if st in ("error", "failure"):
        msg = str(r.get("error_message") or "")[:180]
        print(f"{r.get('started_at')} {r.get('source')} {st}: {msg}")
'@ | docker exec -i ph-eye-worker python -

Write-Host ""
Write-Host "2) Last 4h worker log quality signals"
Write-Host "----------------------------------------------------------------------"
$workerLogs = docker logs --since 4h ph-eye-worker 2>$null

if (-not $workerLogs) {
  Write-Host "No worker logs captured."
  exit 0
}

$patterns = @{
  "timeouts_total" = "Timeout \d+ms exceeded";
  "dns_failures" = "Temporary failure in name resolution|ERR_NAME_NOT_RESOLVED|name resolution";
  "brotli_failures" = "Brotli decompression failed";
  "section_discovery_failures" = "Section discovery failed";
  "task_success" = "Task app\.workers\.tasks\.scrape_.* succeeded";
  "task_retries" = "retrying\.\.\.|Retry in";
}

foreach ($key in $patterns.Keys) {
  $count = ($workerLogs | Select-String -Pattern $patterns[$key]).Count
  Write-Host ("{0,-28} {1,6}" -f $key, $count)
}

Write-Host ""
Write-Host "3) Per-source timeout indicators (last 4h)"
Write-Host "----------------------------------------------------------------------"
$sourcePatterns = @{
  "inquirer" = "inquirer.*Timeout|Inquirer: attempt .*Timeout";
  "philstar" = "philstar.*Timeout|Failed to scrape https://www\.philstar\.com";
  "rappler" = "rappler.*Timeout|Section discovery failed for .*";
  "manila_bulletin" = "mb\.com\.ph.*Timeout|Homepage discovery failed: Page\.goto: Timeout";
  "manila_times" = "manilatimes.*Timeout|manila_times: Request error";
  "gma" = "gmanetwork.*Timeout|GMA v1: error loading";
  "sunstar" = "sunstar.*Timeout|Sunstar.*error";
}

foreach ($src in $sourcePatterns.Keys) {
  $count = ($workerLogs | Select-String -Pattern $sourcePatterns[$src]).Count
  Write-Host ("{0,-16} {1,6}" -f $src, $count)
}

Write-Host ""
Write-Host "Done."
