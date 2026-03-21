from __future__ import annotations

from datetime import datetime, timezone
import logging

from celery import shared_task

from app.core.supabase import get_supabase
from app.ml.bias import build_comprehensive_bias_analysis

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_articles_task(self, article_ids: list[int]):
    sb = get_supabase()
    try:
        # Fetch articles
        res = sb.table("articles").select("*").in_("id", article_ids).execute()
        rows = res.data or []

        out_rows: list[dict] = []
        for r in rows:
            article_id = r.get("id")
            # Preserve title/body boundary for long-form sentiment weighting.
            text = f"{str(r.get('title') or '').strip()}\n\n{str(r.get('content') or '').strip()}".strip()
            out_rows.extend(build_comprehensive_bias_analysis(int(article_id), text))

        inserted = 0
        if out_rows:
            ins = sb.table("bias_analysis").upsert(out_rows, on_conflict="article_id,model_version,model_type").execute()
            inserted = len(ins.data or [])

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
                    sb.table("article_sentiment_public").upsert(sent_rows, on_conflict="article_id").execute()
            except Exception as e:
                # Don't fail the ML task if the demo table isn't created yet.
                logger.warning("article_sentiment_public upsert failed (demo mode): %s", e)

        return {"ok": True, "articles": len(rows), "inserted": inserted}
    except Exception as e:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        return {"ok": False, "error": str(e), "articles": 0, "inserted": 0}

