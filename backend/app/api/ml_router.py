import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, Header

from app.cache import get_cached, set_cached
from app.core.supabase import get_supabase
from app.ml.bias import get_political_keywords_and_weights
from app.services.analytics_service import aggregate_entities_with_sentiment, clean_entity_for_counting
from app.services.articles_service import get_all_articles_paginated
from app.services.window_service import window_bounds
from app.workers.ml_tasks import analyze_articles_task


router = APIRouter()


# Simple token guard using env ADMIN_TOKEN (optional)
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")


@router.get("/ml/keywords/status")
async def get_keywords_status():
    try:
        kw, weights, version = get_political_keywords_and_weights()
        categories = {k: len(v or []) for k, v in (kw or {}).items()}
        return {"ok": True, "version": version, "categories": categories, "weights_present": bool(weights)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/ml/keywords/suggestions")
async def get_keywords_suggestions(x_admin_token: Optional[str] = Header(default=None)):
    if ADMIN_TOKEN and x_admin_token != ADMIN_TOKEN:
        return {"ok": False, "error": "unauthorized"}
    sugg_path = os.path.join(os.path.dirname(__file__), "ml", "suggestions", "keywords_ph_suggestions.json")
    try:
        with open(sugg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"ok": True, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/ml/keywords/apply_suggestions")
async def apply_keywords_suggestions(
    category: str = Body(default="neutral_institutional"),
    apply: bool = Body(default=True),
    x_admin_token: Optional[str] = Header(default=None),
):
    if ADMIN_TOKEN and x_admin_token != ADMIN_TOKEN:
        return {"ok": False, "error": "unauthorized"}
    backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    script_path = os.path.join(backend_root, "scripts", "apply_keywords_suggestions.py")
    if not os.path.exists(script_path):
        return {"ok": False, "error": f"script not found: {script_path}"}
    cmd = [sys.executable, script_path, "--category", category]
    if apply:
        cmd.append("--apply")
    try:
        proc = subprocess.Popen(cmd, cwd=backend_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate(timeout=60)
        return {
            "ok": proc.returncode == 0,
            "stdout": out.decode("utf-8", "ignore"),
            "stderr": err.decode("utf-8", "ignore"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/ml/correlation")
async def get_sentiment_correlation(
    period: str = "7d",
    sources: Optional[str] = None,
    include_today: bool = True,
    refresh: bool = False,
    with_entities: bool = False,
    ner_exclude_sources: Optional[str] = None,
):
    """Compute Pearson correlation between sources' daily average sentiment.

    - period: 7d|30d
    - sources: comma-separated list of source names; defaults to all in window
    - include_today: include partial data for the current local PH day
    - with_entities: reserved for future entity+sentiment fusion payload
    """
    import numpy as _np
    from collections import defaultdict as _dd
    from zoneinfo import ZoneInfo as _ZoneInfo

    tz_ph = _ZoneInfo("Asia/Manila")
    now_local = datetime.now(tz_ph)
    if period == "7d":
        window_days = 7
    elif period == "30d":
        window_days = 30
    else:
        window_days = 7

    if include_today:
        end_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)
        start_local = (now_local - timedelta(days=window_days - 1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    else:
        end_local = (now_local - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        start_local = (end_local - timedelta(days=window_days - 1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    end_date = end_local.astimezone(ZoneInfo("UTC"))
    start_date = start_local.astimezone(ZoneInfo("UTC"))
    start_date_str = start_date.isoformat()
    end_date_str = end_date.isoformat()

    cache_key = (
        f"corr:{period}:{sources or 'all'}:today:{'1' if include_today else '0'}:"
        f"entities:{'1' if with_entities else '0'}:nerX:{(ner_exclude_sources or 'none')}::"
        f"start:{start_date_str[:10]}:end:{end_date_str[:10]}"
    )
    if not refresh:
        cached = get_cached(cache_key)
        if cached:
            return cached

    sb = get_supabase()

    def to_ph_date_str(ts: str) -> str:
        try:
            dt = datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
            return dt.astimezone(tz_ph).date().isoformat()
        except Exception:
            return (ts or "")[:10]

    # Build source filter
    source_filter = None
    source_set = None
    if sources:
        filter_set = {s.strip() for s in sources.split(",") if s.strip()}
        if len(filter_set) == 1:
            source_filter = list(filter_set)[0]
        else:
            source_set = filter_set

    all_articles = get_all_articles_paginated(
        sb,
        start_date_str,
        source_filter,
        end_date=end_date_str,
        select_fields="id,source,published_at",
    )

    if source_set:
        all_articles = [a for a in all_articles if (a.get("source") or "").strip() in source_set]

    if not all_articles:
        result = {"ok": True, "sources": [], "matrix": [], "p_values": [], "dates": []}
        set_cached(cache_key, result, 120)
        return result

    article_ids = [a["id"] for a in all_articles]
    article_id_set = set(article_ids)

    all_analysis = []
    batch_size = 2000
    for i in range(0, len(article_ids), batch_size):
        batch_ids = article_ids[i : i + batch_size]
        try:
            res = (
                sb.table("bias_analysis")
                .select("article_id,sentiment_score,model_type")
                .in_("article_id", batch_ids)
                .eq("model_type", "sentiment")
                .execute()
            )
            all_analysis.extend(res.data or [])
        except Exception:
            if batch_size > 500:
                batch_size = 500
                continue
            raise

    id_to_meta = {}
    for a in all_articles:
        id_to_meta[a["id"]] = ((a.get("source") or "unknown"), to_ph_date_str(a.get("published_at", "")))

    per_source_date_scores = _dd(lambda: _dd(list))
    for row in all_analysis:
        aid = row.get("article_id")
        score = row.get("sentiment_score")
        if aid not in article_id_set or score is None:
            continue
        if aid not in id_to_meta:
            continue
        src, d = id_to_meta[aid]
        if not d:
            continue
        per_source_date_scores[src][d].append(float(score))

    per_source_series = _dd(dict)
    for src, dmap in per_source_date_scores.items():
        for d, vals in dmap.items():
            if not vals:
                continue
            per_source_series[src][d] = float(sum(vals) / len(vals))

    src_names = sorted(per_source_series.keys())
    n = len(src_names)
    if n == 0:
        result = {"ok": True, "sources": [], "matrix": [], "p_values": [], "dates": []}
        set_cached(cache_key, result, 120)
        return result

    matrix = [[None for _ in range(n)] for _ in range(n)]
    pvals = [[None for _ in range(n)] for _ in range(n)]

    _scipy_stats = None
    try:
        from scipy import stats as _stats  # type: ignore

        _scipy_stats = _stats
    except Exception:
        _scipy_stats = None

    for i, sa in enumerate(src_names):
        matrix[i][i] = 1.0
        pvals[i][i] = 0.0
        for j in range(i + 1, n):
            sb_name = src_names[j]
            dates_intersection = sorted(set(per_source_series[sa].keys()) & set(per_source_series[sb_name].keys()))
            if len(dates_intersection) < 3:
                r = None
                p = None
            else:
                a_vals = [_np.float64(per_source_series[sa][d]) for d in dates_intersection]
                b_vals = [_np.float64(per_source_series[sb_name][d]) for d in dates_intersection]
                try:
                    r = float(_np.corrcoef(a_vals, b_vals)[0, 1])
                    if _scipy_stats is not None:
                        try:
                            r2, p2 = _scipy_stats.pearsonr(a_vals, b_vals)
                            r = float(r2)
                            p = float(p2)
                        except Exception:
                            p = None
                    else:
                        p = None
                except Exception:
                    r = None
                    p = None
            matrix[i][j] = r
            matrix[j][i] = r
            pvals[i][j] = p
            pvals[j][i] = p

    result = {"ok": True, "period": period, "include_today": include_today, "sources": src_names, "matrix": matrix, "p_values": pvals}

    if with_entities:
        try:
            exclude_set = {s.strip() for s in (ner_exclude_sources or "").split(",") if s.strip()}
            article_ids_with_sentiment = {row.get("article_id") for row in all_analysis if row.get("article_id")}
            articles_for_ner = {}
            if article_ids_with_sentiment:
                ner_batch_size = 500
                ids_list = list(article_ids_with_sentiment)
                for i in range(0, len(ids_list), ner_batch_size):
                    batch_ids = ids_list[i : i + ner_batch_size]
                    try:
                        ner_res = sb.table("articles").select("id,title,content,source").in_("id", batch_ids).execute()
                        for a in (ner_res.data or []):
                            articles_for_ner[a["id"]] = a
                    except Exception:
                        continue
            top, _ = aggregate_entities_with_sentiment(
                analysis_rows=all_analysis,
                articles_by_id=articles_for_ner,
                exclude_set=exclude_set,
                max_entities=20,
            )
            result["entities"] = top
        except Exception:
            result["entities"] = []

    set_cached(cache_key, result, 120 if include_today else 600)
    return result


@router.get("/ml/entities/top")
async def get_top_entities(
    period: str = "30d",
    source: Optional[str] = None,
    include_today: bool = True,
    refresh: bool = False,
    limit_articles: int = 500,
    total_cap: int = 1000,
    max_entities: int = 100,
    scan_mode: str = "fast",
    ner_exclude_sources: Optional[str] = None,
):
    sb = get_supabase()
    start_date_str, end_date_str = window_bounds(period, include_today=include_today)

    cache_key = (
        f"entities_top:{period}:{source or 'all'}:today:{'1' if include_today else '0'}:"
        f"limit:{limit_articles}:cap:{total_cap}:max:{max_entities}:scan:{scan_mode}:"
        f"nerX:{(ner_exclude_sources or 'none')}:start:{start_date_str[:10]}:end:{end_date_str[:10]}"
    )
    if not refresh:
        cached = get_cached(cache_key)
        if cached:
            return cached

    try:
        all_articles = get_all_articles_paginated(
            sb,
            start_date_str,
            source=source,
            end_date=end_date_str,
            select_fields="id,source,published_at,title,content",
        )
        total_available = len(all_articles)
        total_capped = min(total_available, max(1, total_cap))
        capped_articles = all_articles[:total_capped]

        if scan_mode == "full":
            sampled_articles = capped_articles
            sample_cap = total_capped
        else:
            sample_cap = max(1, min(limit_articles, total_capped))
            sampled_articles = capped_articles[:sample_cap]

        if not sampled_articles:
            result = {
                "ok": True,
                "sampled": 0,
                "sample_cap": sample_cap,
                "total_cap": total_cap,
                "total_available": total_available,
                "total_capped": total_capped,
                "scan_mode": scan_mode,
                "top_entities": [],
            }
            set_cached(cache_key, result, 120)
            return result

        articles_by_id = {a["id"]: a for a in sampled_articles if a.get("id")}
        article_ids = list(articles_by_id.keys())

        all_analysis = []
        batch_size = 2000
        for i in range(0, len(article_ids), batch_size):
            batch_ids = article_ids[i : i + batch_size]
            res = (
                sb.table("bias_analysis")
                .select("article_id,sentiment_score,model_type,created_at")
                .in_("article_id", batch_ids)
                .eq("model_type", "sentiment")
                .order("created_at", desc=True)
                .execute()
            )
            all_analysis.extend(res.data or [])

        # Deduplicate to latest sentiment per article.
        latest_by_article = {}
        for row in all_analysis:
            aid = row.get("article_id")
            if aid and aid not in latest_by_article:
                latest_by_article[aid] = row
        analysis_rows = list(latest_by_article.values())

        exclude_set = {s.strip() for s in (ner_exclude_sources or "").split(",") if s.strip()}
        top_entities, analyzed_articles = aggregate_entities_with_sentiment(
            analysis_rows=analysis_rows,
            articles_by_id=articles_by_id,
            exclude_set=exclude_set,
            max_entities=max_entities,
        )

        result = {
            "ok": True,
            "sampled": analyzed_articles,
            "sample_cap": sample_cap,
            "total_cap": total_cap,
            "total_available": total_available,
            "total_capped": total_capped,
            "scan_mode": scan_mode,
            "top_entities": top_entities,
        }
        set_cached(cache_key, result, 120 if include_today else 600)
        return result
    except Exception as e:
        return {"ok": False, "error": str(e), "top_entities": []}


@router.get("/ml/ner/sample")
async def ner_sample(
    days_back: int = 7,
    limit: int = 20,
    source: Optional[str] = None,
    ner_exclude_sources: Optional[str] = None,
):
    """Run spaCy NER on a recent sample of articles to verify entity extraction.
    Returns top entities and per-article examples with extracted entities.
    """
    try:
        sb = get_supabase()
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=days_back)
        q = (
            sb.table("articles")
            .select("id,title,content,source,published_at")
            .gte("published_at", start_dt.isoformat())
            .lte("published_at", end_dt.isoformat())
            .order("published_at", desc=True)
            .limit(limit)
        )
        if source:
            q = q.eq("source", source)
        res = q.execute()
        articles = res.data or []

        if not articles:
            return {"ok": True, "articles": [], "top_entities": [], "note": "No recent articles found"}

        from app.nlp.spacy_nlp import extract_entities as _extract_entities
        from collections import Counter

        entity_counter = Counter()
        exclude_set = {s.strip() for s in (ner_exclude_sources or "").split(",") if s.strip()}
        examples = []

        for a in articles:
            if exclude_set and (a.get("source") or "").strip() in exclude_set:
                continue

            text = f"{a.get('title','')}\n{a.get('content','')}"
            ents = _extract_entities(text)

            filtered_ents = []
            for e in ents:
                cleaned = clean_entity_for_counting(e.get("text", ""), e.get("label", ""))
                if not cleaned:
                    continue
                _norm_text, clean_label, display_text = cleaned
                filtered_ents.append(
                    {
                        "text": display_text,
                        "label": clean_label,
                        "start": e.get("start"),
                        "end": e.get("end"),
                    }
                )

            examples.append(
                {
                    "id": a.get("id"),
                    "source": a.get("source"),
                    "published_at": a.get("published_at"),
                    "entities": filtered_ents[:25],
                }
            )

            for e in filtered_ents:
                entity_counter[(e["text"], e["label"])] += 1

        top_entities = []
        for (text, k), c in entity_counter.most_common(30):
            top_entities.append({"text": text, "type": k, "mentions": c})

        return {"ok": True, "sampled": len(articles), "top_entities": top_entities, "articles": examples}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/ml/analyze")
async def analyze_articles(payload: dict = Body(default={})):
    article_ids = payload.get("article_ids")
    since = payload.get("since")

    if not article_ids and not since:
        return {"error": "Either article_ids or since must be provided"}

    sb = get_supabase()

    if since:
        # Get articles from the specified date
        try:
            result = sb.table("articles").select("id").gte("published_at", since).execute()
            article_ids = [row["id"] for row in result.data or []]
        except Exception as e:
            return {"error": f"Failed to fetch articles: {e}"}

    if not article_ids:
        return {"error": "No articles found for analysis"}

    # Queue analysis task
    try:
        task = analyze_articles_task.delay(article_ids)
        return {"queued": True, "task_id": str(task), "article_count": len(article_ids)}
    except Exception as e:
        return {"error": f"Failed to queue analysis: {e}"}


@router.get("/ml/analysis")
async def get_analysis(ids: str):
    try:
        article_ids = [int(id.strip()) for id in ids.split(",") if id.strip()]
    except ValueError:
        return {"error": "Invalid article IDs format"}

    sb = get_supabase()
    try:
        result = (
            sb.table("bias_analysis")
            .select("*")
            .in_("article_id", article_ids)
            .order("created_at", desc=True)
            .limit(50000)
            .execute()
        )
        return {"analysis": result.data or []}
    except Exception as e:
        return {"error": str(e)}


@router.get("/ml/trends")
async def get_trends(period: str = "7d", source: Optional[str] = None, include_today: bool = True, refresh: bool = False):
    sb = get_supabase()

    # Calculate date range using Asia/Manila local day boundaries, then convert to UTC for querying
    from datetime import timezone

    tz_ph = ZoneInfo("Asia/Manila")
    now_local = datetime.now(tz_ph)

    if period == "7d":
        window_days = 7
    elif period == "30d":
        window_days = 30
    else:
        window_days = 7

    if include_today:
        end_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)
        start_local = (now_local - timedelta(days=window_days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        end_local = (now_local - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        start_local = (end_local - timedelta(days=window_days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    end_date = end_local.astimezone(timezone.utc)
    start_date = start_local.astimezone(timezone.utc)
    start_date_str = start_date.isoformat()
    end_date_str = end_date.isoformat()

    cache_key = f"trends:{period}:{source or 'all'}:today:{'1' if include_today else '0'}:start:{start_date_str[:10]}:end:{end_date_str[:10]}"
    cached_result = None if refresh else get_cached(cache_key)
    if cached_result:
        return cached_result

    try:
        articles = get_all_articles_paginated(sb, start_date_str, source, end_date=end_date_str)

        if not articles:
            result = {
                "ok": True,
                "summary": {
                    "period": period,
                    "source": source,
                    "total_articles": 0,
                    "positive_pct": 0,
                    "negative_pct": 0,
                    "neutral_pct": 0,
                    "avg_daily_articles": 0,
                },
                "timeline": [],
            }
            set_cached(cache_key, result, 60)
            return result

        article_ids = [a["id"] for a in articles]
        all_analysis = []
        batch_size = 500

        for i in range(0, len(article_ids), batch_size):
            batch_ids = article_ids[i : i + batch_size]
            analysis_result = (
                sb.table("bias_analysis").select("*").in_("article_id", batch_ids).eq("model_type", "sentiment").execute()
            )
            all_analysis.extend(analysis_result.data or [])

        from collections import defaultdict

        daily_data = defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0, "total": 0, "sentiment_scores": []})

        def to_ph_date_str(ts: str) -> str:
            try:
                dt = datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
                return dt.astimezone(tz_ph).date().isoformat()
            except Exception:
                return (ts or "")[:10]

        for article in articles:
            date_str = to_ph_date_str(article.get("published_at", ""))
            daily_data[date_str]["total"] += 1

        for analysis in all_analysis:
            article_id = analysis["article_id"]
            sentiment_label = analysis.get("sentiment_label", "neutral")
            sentiment_score = analysis.get("sentiment_score", 0)

            article = next((a for a in articles if a["id"] == article_id), None)
            if article:
                date_str = to_ph_date_str(article.get("published_at", ""))
                daily_data[date_str]["sentiment_scores"].append(sentiment_score)

                if sentiment_label == "positive":
                    daily_data[date_str]["positive"] += 1
                elif sentiment_label == "negative":
                    daily_data[date_str]["negative"] += 1
                else:
                    daily_data[date_str]["neutral"] += 1

        timeline = []
        total_articles = 0
        total_positive = 0
        total_negative = 0
        total_neutral = 0

        aggregated_daily_data = defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0, "total": 0, "sentiment_scores": []})

        for date_str, data in daily_data.items():
            aggregated_daily_data[date_str]["total"] += data["total"]
            aggregated_daily_data[date_str]["positive"] += data["positive"]
            aggregated_daily_data[date_str]["negative"] += data["negative"]
            aggregated_daily_data[date_str]["neutral"] += data["neutral"]
            aggregated_daily_data[date_str]["sentiment_scores"].extend(data["sentiment_scores"])

        window_start_local = start_local.date()
        window_end_local = end_local.date()
        for date_str in sorted(aggregated_daily_data.keys()):
            try:
                date_obj = datetime.fromisoformat(date_str).date()
            except Exception:
                date_obj = None
            if date_obj and not (window_start_local <= date_obj <= window_end_local):
                continue
            data = aggregated_daily_data[date_str]
            total = data["total"]
            positive = data["positive"]
            negative = data["negative"]
            neutral = data["neutral"]

            total_articles += total
            total_positive += positive
            total_negative += negative
            total_neutral += neutral

            avg_sentiment = sum(data["sentiment_scores"]) / len(data["sentiment_scores"]) if data["sentiment_scores"] else 0

            timeline.append(
                {
                    "date": date_str,
                    "positive": positive,
                    "negative": negative,
                    "neutral": neutral,
                    "total": total,
                    "avg_sentiment": avg_sentiment,
                    "positive_pct": round((positive / total * 100) if total > 0 else 0, 1),
                    "negative_pct": round((negative / total * 100) if total > 0 else 0, 1),
                    "neutral_pct": round((neutral / total * 100) if total > 0 else 0, 1),
                }
            )

        positive_pct = round((total_positive / total_articles * 100) if total_articles > 0 else 0, 1)
        negative_pct = round((total_negative / total_articles * 100) if total_articles > 0 else 0, 1)
        neutral_pct = round((total_neutral / total_articles * 100) if total_articles > 0 else 0, 1)
        avg_daily_articles = round(total_articles / len(timeline), 1) if timeline else 0

        result = {
            "ok": True,
            "summary": {
                "period": period,
                "source": source,
                "total_articles": total_articles,
                "positive_pct": positive_pct,
                "negative_pct": negative_pct,
                "neutral_pct": neutral_pct,
                "avg_daily_articles": avg_daily_articles,
            },
            "timeline": timeline,
        }

        set_cached(cache_key, result, 60 if include_today else 300)
        return result

    except Exception as e:
        return {"error": str(e)}


@router.get("/ml/bias_analysis_political_latest")
async def get_political_bias_latest(limit: int = 100):
    """Get latest political bias analysis results."""
    sb = get_supabase()
    try:
        result = (
            sb.table("bias_analysis")
            .select("*")
            .eq("model_version", "philippine_bias_v1")
            .eq("model_type", "political_bias")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        return {"error": str(e)}


@router.get("/dashboard/comprehensive")
async def get_comprehensive_dashboard(period: str = "7d", source: Optional[str] = None):
    """Comprehensive dashboard data including both sentiment and political bias analysis."""
    sb = get_supabase()

    now = datetime.now()

    if period == "1d":
        start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == "7d":
        start_date = (now - timedelta(days=8)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == "30d":
        start_date = (now - timedelta(days=31)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        start_date = (now - timedelta(days=8)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)

    start_date_str = start_date.isoformat()

    try:
        articles = get_all_articles_paginated(sb, start_date_str, source)

        if not articles:
            return {
                "ok": True,
                "articles": {"total": 0, "by_source": {}, "by_date": {}},
                "sentiment": {"total_analyses": 0, "avg_compound": 0, "distribution": {"positive": 0, "neutral": 0, "negative": 0}},
                "political_bias": {"total_analyses": 0, "avg_bias_score": 0, "avg_confidence": 0, "distribution": {"pro_government": 0, "pro_opposition": 0, "neutral": 0, "mixed": 0}},
                "source_comparison": [],
                "timeline": [],
                "generated_at": now.isoformat(),
            }

        article_ids = [a["id"] for a in articles]
        sentiment_result = (
            sb.table("bias_analysis")
            .select("*")
            .in_("article_id", article_ids)
            .eq("model_version", "vader_v1")
            .eq("model_type", "sentiment")
            .execute()
        )
        sentiment_data = sentiment_result.data or []

        political_result = (
            sb.table("bias_analysis")
            .select("*")
            .in_("article_id", article_ids)
            .eq("model_version", "philippine_bias_v1")
            .eq("model_type", "political_bias")
            .execute()
        )
        political_data = political_result.data or []

        sentiment_scores = [s.get("sentiment_score", 0) for s in sentiment_data if s.get("sentiment_score") is not None]
        sentiment_labels = [s.get("sentiment_label", "neutral") for s in sentiment_data]

        sentiment_distribution = {"positive": 0, "neutral": 0, "negative": 0}
        for label in sentiment_labels:
            if label in sentiment_distribution:
                sentiment_distribution[label] += 1

        political_scores = [p.get("political_bias_score", 0) for p in political_data if p.get("political_bias_score") is not None]
        political_directions = [p.get("model_metadata", {}).get("direction", "neutral") for p in political_data]

        political_distribution = {"pro_government": 0, "pro_opposition": 0, "neutral": 0, "mixed": 0}
        for direction in political_directions:
            if direction in political_distribution:
                political_distribution[direction] += 1

        by_source = {}
        for article in articles:
            source_name = article.get("source", "Unknown")
            by_source[source_name] = by_source.get(source_name, 0) + 1

        by_date = {}
        for article in articles:
            date_str = article.get("published_at", "")[:10]
            if date_str:
                by_date[date_str] = by_date.get(date_str, 0) + 1

        timeline = []
        for date_str in sorted(by_date.keys()):
            day_articles = [a for a in articles if a.get("published_at", "").startswith(date_str)]
            day_article_ids = [a["id"] for a in day_articles]

            day_sentiment = [s for s in sentiment_data if s.get("article_id") in day_article_ids]
            day_political = [p for p in political_data if p.get("article_id") in day_article_ids]

            day_sentiment_scores = [s.get("sentiment_score", 0) for s in day_sentiment if s.get("sentiment_score") is not None]
            day_political_scores = [p.get("political_bias_score", 0) for p in day_political if p.get("political_bias_score") is not None]
            day_political_confidences = [p.get("confidence_score", 0) for p in day_political if p.get("confidence_score") is not None]

            timeline.append(
                {
                    "date": date_str,
                    "articles": len(day_articles),
                    "sentiment": {
                        "avg_score": sum(day_sentiment_scores) / len(day_sentiment_scores) if day_sentiment_scores else 0,
                        "distribution": {
                            "positive": len([s for s in day_sentiment if s.get("sentiment_label") == "positive"]),
                            "neutral": len([s for s in day_sentiment if s.get("sentiment_label") == "neutral"]),
                            "negative": len([s for s in day_sentiment if s.get("sentiment_label") == "negative"]),
                        },
                    },
                    "political_bias": {
                        "avg_bias_score": sum(day_political_scores) / len(day_political_scores) if day_political_scores else 0,
                        "avg_confidence": sum(day_political_confidences) / len(day_political_confidences) if day_political_confidences else 0,
                        "distribution": {
                            "pro_government": len([p for p in day_political if p.get("model_metadata", {}).get("direction") == "pro_government"]),
                            "pro_opposition": len([p for p in day_political if p.get("model_metadata", {}).get("direction") == "pro_opposition"]),
                            "neutral": len([p for p in day_political if p.get("model_metadata", {}).get("direction") == "neutral"]),
                        },
                    },
                }
            )

        source_comparison = []
        for source_name, count in by_source.items():
            source_articles = [a for a in articles if a.get("source") == source_name]
            source_article_ids = [a["id"] for a in source_articles]

            source_sentiment = [s for s in sentiment_data if s.get("article_id") in source_article_ids]
            source_political = [p for p in political_data if p.get("article_id") in source_article_ids]

            source_political_scores = [p.get("political_bias_score", 0) for p in source_political if p.get("political_bias_score") is not None]
            source_political_confidences = [p.get("confidence_score", 0) for p in source_political if p.get("confidence_score") is not None]

            source_political_distribution = {"pro_government": 0, "pro_opposition": 0, "neutral": 0}
            for p in source_political:
                direction = p.get("model_metadata", {}).get("direction", "neutral")
                if direction in source_political_distribution:
                    source_political_distribution[direction] += 1

            source_comparison.append(
                {
                    "source": source_name,
                    "article_count": count,
                    "political_bias": {
                        "avg_bias_score": sum(source_political_scores) / len(source_political_scores) if source_political_scores else 0,
                        "avg_confidence": sum(source_political_confidences) / len(source_political_confidences) if source_political_confidences else 0,
                        "distribution": source_political_distribution,
                    },
                }
            )

        return {
            "ok": True,
            "articles": {"total": len(articles), "by_source": by_source, "by_date": by_date},
            "sentiment": {"total_analyses": len(sentiment_data), "avg_compound": sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0, "distribution": sentiment_distribution},
            "political_bias": {
                "total_analyses": len(political_data),
                "avg_bias_score": sum(political_scores) / len(political_scores) if political_scores else 0,
                "avg_confidence": (
                    sum([p.get("confidence_score", 0) for p in political_data if p.get("confidence_score") is not None])
                    / len([p for p in political_data if p.get("confidence_score") is not None])
                    if political_data
                    else 0
                ),
                "distribution": political_distribution,
            },
            "source_comparison": source_comparison,
            "timeline": timeline,
            "generated_at": now.isoformat(),
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}
