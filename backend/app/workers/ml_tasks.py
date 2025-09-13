from celery import shared_task
from app.core.supabase import get_supabase
from app.ml.bias import build_bias_row_for_vader

@shared_task(bind=True, max_retries=0)
def analyze_articles_task(self, article_ids: list[int]):
    sb = get_supabase()
    # Fetch articles
    res = sb.table("articles").in_("id", article_ids).execute()
    rows = res.data or []

    out_rows = []
    for r in rows:
        article_id = r.get("id")
        text = " ".join([str(r.get("title") or ""), str(r.get("content") or "")]).strip()
        out_rows.append(build_bias_row_for_vader(int(article_id), text))

    inserted = 0
    if out_rows:
        # Use composite unique index as comma-separated list
        ins = sb.table("bias_analysis").upsert(out_rows, on_conflict="article_id,model_version,model_type").execute()
        inserted = len(ins.data or [])

    return {"ok": True, "articles": len(rows), "inserted": inserted} 