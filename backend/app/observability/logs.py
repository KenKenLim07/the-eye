from datetime import datetime, timezone
from typing import Optional, TypedDict

from app.core.supabase import get_supabase


class ScrapeLogRecord(TypedDict):
    id: int
    run_id: str
    source: str
    started_at: str


def start_run(source: str) -> ScrapeLogRecord:
    sb = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    # Initial status as 'partial' to indicate in-progress
    res = sb.table("scraping_logs").insert({
        "source": source,
        "status": "partial",
        "started_at": now,
    }).execute()
    row = (res.data or [])[0]
    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "source": row["source"],
        "started_at": row["started_at"],
    }


def finalize_run(log_id: int, *, status: str, articles_scraped: int = 0, error_message: Optional[str] = None) -> None:
    sb = get_supabase()
    completed = datetime.now(timezone.utc).isoformat()
    sb.table("scraping_logs").update({
        "status": status,
        "articles_scraped": max(0, int(articles_scraped or 0)),
        "error_message": error_message,
        "completed_at": completed,
    }).eq("id", log_id).execute() 