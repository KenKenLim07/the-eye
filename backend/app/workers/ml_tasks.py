from __future__ import annotations

from datetime import datetime, timezone
import logging
import os

from celery import shared_task

from app.core.supabase import get_supabase
from app.ml.bias import build_comprehensive_bias_analysis

logger = logging.getLogger(__name__)


def _chunked(items: list, size: int) -> list[list]:
    if size <= 0:
        return [items]
    return [items[i : i + size] for i in range(0, len(items), size)]


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_articles_task(self, article_ids: list[int]):
    sb = get_supabase()
    try:
        fetch_chunk = int(os.getenv("ML_FETCH_CHUNK_SIZE") or "50")
        upsert_chunk = int(os.getenv("ML_UPSERT_CHUNK_SIZE") or "500")
        progress_every = int(os.getenv("ML_PROGRESS_EVERY") or "25")

        # Fetch articles (chunked to avoid massive `id=in.(...)` URLs and timeouts).
        rows: list[dict] = []
        for idx, batch in enumerate(_chunked(article_ids, fetch_chunk), start=1):
            res = sb.table("articles").select("*").in_("id", batch).execute()
            rows.extend(res.data or [])
            if len(article_ids) > fetch_chunk:
                logger.info(
                    "ML fetch chunk %d/%d: %d ids",
                    idx,
                    (len(article_ids) + fetch_chunk - 1) // fetch_chunk,
                    len(batch),
                )

        out_rows: list[dict] = []
        total = len(rows)
        for i, r in enumerate(rows, start=1):
            article_id = r.get("id")
            # Preserve title/body boundary for long-form sentiment weighting.
            text = f"{str(r.get('title') or '').strip()}\n\n{str(r.get('content') or '').strip()}".strip()
            out_rows.extend(build_comprehensive_bias_analysis(int(article_id), text))
            if progress_every > 0 and (i % progress_every == 0 or i == total):
                logger.info("ML analyze progress: %d/%d articles", i, total)

        inserted = 0
        if out_rows:
            # Chunked upsert avoids very large payloads/timeouts.
            for idx, batch in enumerate(_chunked(out_rows, upsert_chunk), start=1):
                ins = sb.table("bias_analysis").upsert(batch, on_conflict="article_id,model_version,model_type").execute()
                inserted += len(ins.data or [])
                if len(out_rows) > upsert_chunk:
                    logger.info(
                        "ML upsert chunk %d/%d: %d rows",
                        idx,
                        (len(out_rows) + upsert_chunk - 1) // upsert_chunk,
                        len(batch),
                    )

            # Demo-mode helper: store the latest sentiment per article in a public-readable table.
            # This lets the deployed frontend show VADER badges without a deployed FastAPI backend.
            try:
                now_iso = datetime.now(timezone.utc).isoformat()
                sent_rows = []
                for r in out_rows:
                    if (r.get("model_type") or "").strip() != "sentiment":
                        continue
                    aid = r.get("article_id")
                    if aid is None:
                        continue
                    sent_rows.append(
                        {
                            "article_id": int(aid),
                            "sentiment_label": r.get("sentiment_label"),
                            "sentiment_score": r.get("sentiment_score"),
                            "updated_at": now_iso,
                        }
                    )
                if sent_rows:
                    for batch in _chunked(sent_rows, upsert_chunk):
                        sb.table("article_sentiment_public").upsert(batch, on_conflict="article_id").execute()
            except Exception as e:
                # Don't fail the ML task if the demo table isn't created yet.
                logger.warning("article_sentiment_public upsert failed (demo mode): %s", e)

        return {"ok": True, "articles": len(rows), "inserted": inserted}
    except Exception as e:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        return {"ok": False, "error": str(e), "articles": 0, "inserted": 0}
