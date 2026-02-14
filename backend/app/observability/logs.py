from datetime import datetime, timezone
from typing import Optional, TypedDict
import time
import logging

from app.core.supabase import get_supabase

logger = logging.getLogger(__name__)


class ScrapeLogRecord(TypedDict):
    id: int
    run_id: str
    source: str
    started_at: str


def start_run(source: str, max_retries: int = 3) -> ScrapeLogRecord:
    """Start a scraping run with retry logic for DNS/network issues."""
    for attempt in range(max_retries):
        try:
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
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 0.5  # Exponential backoff: 0.5s, 1s, 2s
                logger.warning(f"Failed to start run for {source} (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to start run for {source} after {max_retries} attempts: {e}")
                raise


def finalize_run(log_id: int, *, status: str, articles_scraped: int = 0, error_message: Optional[str] = None, max_retries: int = 3) -> None:
    """Finalize a scraping run with retry logic for DNS/network issues."""
    for attempt in range(max_retries):
        try:
            sb = get_supabase()
            completed = datetime.now(timezone.utc).isoformat()
            sb.table("scraping_logs").update({
                "status": status,
                "articles_scraped": max(0, int(articles_scraped or 0)),
                "error_message": error_message,
                "completed_at": completed,
            }).eq("id", log_id).execute()
            return
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 0.5  # Exponential backoff: 0.5s, 1s, 2s
                logger.warning(f"Failed to finalize run {log_id} (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to finalize run {log_id} after {max_retries} attempts: {e}")
                raise 