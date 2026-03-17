from celery import shared_task
from app.core.supabase import get_supabase
from app.ml.bias import build_comprehensive_bias_analysis
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_articles_task(self, article_ids: list[int]):
    sb = get_supabase()
    try:
        # Fetch articles
        res = sb.table("articles").select("*").in_("id", article_ids).execute()
        rows = res.data or []

        out_rows = []
        for r in rows:
            article_id = r.get("id")
            # Preserve title/body boundary for long-form sentiment weighting.
            text = f"{str(r.get('title') or '').strip()}\n\n{str(r.get('content') or '').strip()}".strip()
            out_rows.extend(build_comprehensive_bias_analysis(int(article_id), text))

        inserted = 0
        if out_rows:
            ins = sb.table("bias_analysis").upsert(out_rows, on_conflict="article_id,model_version,model_type").execute()
            inserted = len(ins.data or [])

        return {"ok": True, "articles": len(rows), "inserted": inserted}
    except Exception as e:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        return {"ok": False, "error": str(e), "articles": 0, "inserted": 0}
