from fastapi import FastAPI, Body, Header, Query
from .core.config import settings
from app.workers.tasks import scrape_inquirer_task, scrape_abs_cbn_task, scrape_gma_task, scrape_philstar_task, scrape_manila_bulletin_task, scrape_rappler_task, scrape_sunstar_task, scrape_manila_times_task
from app.workers.celery_app import celery
from celery.result import AsyncResult
from typing import Optional
from app.core.supabase import get_supabase
from app.cache import get_cached, set_cached
from app.workers.ml_tasks import analyze_articles_task
from fastapi.middleware.cors import CORSMiddleware
from app.ml.bias import get_political_keywords_and_weights
import os, json, subprocess, sys
from datetime import datetime, timedelta
from subprocess import Popen, PIPE



def get_all_articles_paginated(sb, start_date, source=None, end_date=None, limit_per_batch=1000):
    """Get ALL articles with proper pagination to bypass 1000-row limit"""
    all_articles = []
    offset = 0
    
    while True:
        query = sb.table('articles').select('*').gte('published_at', start_date).order('published_at', desc=True)
        
        if end_date:
            query = query.lte('published_at', end_date)
        
        if source:
            query = query.eq('source', source)
        
        result = query.range(offset, offset + limit_per_batch - 1).execute()
        articles = result.data or []
        
        if not articles:
            break
            
        all_articles.extend(articles)
        offset += limit_per_batch
        
        # Safety check to prevent infinite loops
        if len(articles) < limit_per_batch:
            break
    return all_articles
    

def get_all_bias_analysis_paginated(sb, start_date, model_type="political_bias", limit_per_batch=1000):
    """Get ALL bias analysis records with proper pagination to bypass 1000-row limit"""
    all_analysis = []
    offset = 0
    
    while True:
        query = sb.table("bias_analysis").select("*, articles(*)").eq("model_type", model_type).gte("created_at", start_date).order("created_at", desc=True)
        
        result = query.range(offset, offset + limit_per_batch - 1).execute()
        analysis_batch = result.data or []
        
        if not analysis_batch:
            break
            
        all_analysis.extend(analysis_batch)
        offset += limit_per_batch
        
        if len(analysis_batch) < limit_per_batch:
            break
            
    return all_analysis
    return all_articles

app = FastAPI(title="PH Eye Backend", version="0.1.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"ok": True, "service": "ph-eye-backend"}

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/scrape/run")
async def run_scrape(payload: dict = Body(default={})):
    # Handle both 'source' (singular) and 'sources' (plural) parameters
    if "source" in payload:
        sources = [payload["source"]]
    elif "sources" in payload:
        sources = payload["sources"]
    else:
        sources = ["inquirer"]  # Default fallback
    
    jobs = []
    for s in sources:
        if s == "inquirer":
            job = scrape_inquirer_task.delay()
            jobs.append({"source": s, "task_id": str(job)})
        elif s in ["abs_cbn", "abs-cbn", "abscbn"]:
            job = scrape_abs_cbn_task.delay()
            jobs.append({"source": "abs_cbn", "task_id": str(job)})
        elif s in ["gma", "gma_news", "gma-news"]:
            job = scrape_gma_task.delay()
            jobs.append({"source": "gma", "task_id": str(job)})
        elif s in ["philstar", "phil_star"]:
            job = scrape_philstar_task.delay()
            jobs.append({"source": "philstar", "task_id": str(job)})
        elif s in ["manila_bulletin", "manila-bulletin", "mb"]:
            job = scrape_manila_bulletin_task.delay()
            jobs.append({"source": "manila_bulletin", "task_id": str(job)})
        elif s in ["rappler", "rappler-news", "rappler-news-ph"]:
            job = scrape_rappler_task.delay()
            jobs.append({"source": "rappler", "task_id": str(job)})
        elif s in ["sunstar", "sunstar-ph", "sunstar-philippines"]:
            job = scrape_sunstar_task.delay()
            jobs.append({"source": "sunstar", "task_id": str(job)})
        elif s in ["manila_times", "manila-times", "mt"]:
            job = scrape_manila_times_task.delay()
            jobs.append({"source": "manila_times", "task_id": str(job)})
    return {"queued": True, "jobs": jobs}

@app.get("/scrape/status/{task_id}")
async def get_scrape_status(task_id: str):
    try:
        result = AsyncResult(task_id, app=celery)
        if result.ready():
            if result.successful():
                return {"status": "completed", "result": result.result}
            else:
                return {"status": "failed", "error": str(result.result)}
        else:
            return {"status": "pending"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/ml/keywords/status")
async def get_keywords_status():
    try:
        kw, weights, version = get_political_keywords_and_weights()
        categories = {k: len(v or []) for k, v in (kw or {}).items()}
        return {
            "ok": True,
            "version": version,
            "categories": categories,
            "weights_present": bool(weights),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

# Simple token guard using env ADMIN_TOKEN (optional)
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN')

@app.get("/ml/keywords/suggestions")
async def get_keywords_suggestions(x_admin_token: Optional[str] = Header(default=None)):
    if ADMIN_TOKEN and x_admin_token != ADMIN_TOKEN:
        return {"ok": False, "error": "unauthorized"}
    sugg_path = os.path.join(os.path.dirname(__file__), 'ml', 'suggestions', 'keywords_ph_suggestions.json')
    try:
        with open(sugg_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {"ok": True, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/ml/keywords/apply_suggestions")
async def apply_keywords_suggestions(category: str = Body(default='neutral_institutional'), apply: bool = Body(default=True), x_admin_token: Optional[str] = Header(default=None)):
    if ADMIN_TOKEN and x_admin_token != ADMIN_TOKEN:
        return {"ok": False, "error": "unauthorized"}
    backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    script_path = os.path.join(backend_root, 'scripts', 'apply_keywords_suggestions.py')
    if not os.path.exists(script_path):
        return {"ok": False, "error": f"script not found: {script_path}"}
    cmd = [sys.executable, script_path, '--category', category]
    if apply:
        cmd.append('--apply')
    try:
        proc = subprocess.Popen(cmd, cwd=backend_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate(timeout=60)
        return {"ok": proc.returncode == 0, "stdout": out.decode('utf-8', 'ignore'), "stderr": err.decode('utf-8', 'ignore')}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/articles")
async def get_articles(limit: int = 50, offset: int = 0, source: Optional[str] = None, category: Optional[str] = None, is_funds: Optional[bool] = None):
    sb = get_supabase()
    
    query = sb.table("articles").select("*")
    
    if source:
        query = query.eq("source", source)
    if category:
        query = query.eq("category", category)
    if is_funds is not None:
        query = query.eq("is_funds", is_funds)
    
    query = query.order("published_at", desc=True).range(offset, offset + limit - 1)
    
    try:
        result = query.execute()
        return {"articles": result.data, "count": len(result.data)}
    except Exception as e:
        return {"error": str(e), "articles": []}

@app.get("/articles/home-optimized")
async def get_home_articles(limit_per_source: int = 10):
    """Optimized endpoint for home page - up to N articles per canonical source with caching."""
    # Generate cache key
    cache_key = f"home_articles:{limit_per_source}"

    # Check cache first
    cached_result = get_cached(cache_key)
    if cached_result:
        return cached_result

    sb = get_supabase()

    try:
        # Define canonical sources shown on the homepage
        sources = [
            "GMA",
            "Rappler",
            "Inquirer",
            "Manila Times",
            "Philstar",
            "Sunstar",
            "Manila Bulletin",
        ]

        articles_by_source = {}

        # Query per source with ordered limit for predictable results
        for src in sources:
            try:
                res = (
                    sb.table("articles")
                    .select("*")
                    .eq("source", src)
                    .order("published_at", desc=True)
                    .limit(limit_per_source)
                    .execute()
                )
                articles_by_source[src] = res.data or []
            except Exception as inner_e:
                # On per-source failure, continue with empty list
                articles_by_source[src] = []

        result_data = {"articles_by_source": articles_by_source}

        # Cache the result (e.g., 10 minutes)
        set_cached(cache_key, result_data, 600)
        return result_data

    except Exception as e:
        return {"error": str(e), "articles_by_source": {}}

@app.get("/articles/{article_id}")
async def get_article(article_id: int):
    sb = get_supabase()
    try:
        result = sb.table("articles").eq("id", article_id).execute()
        if result.data:
            return result.data[0]
        else:
            return {"error": "Article not found"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/articles/{article_id}/analysis")
async def get_article_analysis(article_id: int):
    sb = get_supabase()
    try:
        result = sb.table("bias_analysis").eq("article_id", article_id).order("created_at", desc=True).limit(1).execute()
        if result.data:
            return result.data[0]
        else:
            return {"error": "Analysis not found"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/ml/analyze")
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

@app.get("/ml/analysis")
async def get_analysis(ids: str):
    try:
        article_ids = [int(id.strip()) for id in ids.split(",") if id.strip()]
    except ValueError:
        return {"error": "Invalid article IDs format"}
    
    sb = get_supabase()
    try:
        result = sb.table("bias_analysis").select("*").in_("article_id", article_ids).order("created_at", desc=True).limit(50000).execute()
        return {"analysis": result.data or []}
    except Exception as e:
        return {"error": str(e)}

@app.get("/ml/trends")
async def get_trends(period: str = "7d", source: Optional[str] = None, include_today: bool = True, refresh: bool = False):
    
    sb = get_supabase()
    
    # Calculate date range: use COMPLETE calendar days to avoid partial first/last-day truncation
    from datetime import datetime, timedelta
    now = datetime.now()
    # Default to full, complete days ending yesterday to keep counts stable and avoid partials
    # Allow opting into today's partial data via include_today=true
    # Determine window size in days and compute exact inclusive bounds
    if period == "7d":
        window_days = 7
    elif period == "30d":
        window_days = 30
    else:
        # default to 7 days if unknown
        window_days = 7

    if include_today:
        # Include today → start = today - (window_days - 1)
        end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        start_date = (now - timedelta(days=window_days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        # Exclude today → end = yesterday, start = end - (window_days - 1)
        end_date = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        start_date = (end_date - timedelta(days=window_days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    start_date_str = start_date.isoformat()
    end_date_str = end_date.isoformat()
    # Compute cache key AFTER computing exact date bounds
    cache_key = f"trends:{period}:{source or 'all'}:today:{'1' if include_today else '0'}:start:{start_date_str[:10]}:end:{end_date_str[:10]}"
    # Check cache first (allow force refresh)
    cached_result = None if refresh else get_cached(cache_key)
    if cached_result:
        return cached_result
    
    try:
        # Get articles from the period (with pagination) bounded by end_date
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
                    "avg_daily_articles": 0
                },
                "timeline": []
            }
            # Cache empty result for 1 minute
            set_cached(cache_key, result, 60)
            return result
        
        # Get analysis for these articles (in batches)
        article_ids = [a["id"] for a in articles]
        all_analysis = []
        batch_size = 500
        
        for i in range(0, len(article_ids), batch_size):
            batch_ids = article_ids[i:i + batch_size]
            analysis_result = sb.table("bias_analysis").select("*").in_("article_id", batch_ids).eq("model_type", "sentiment").execute()
            all_analysis.extend(analysis_result.data or [])
        
        # Group by date - FIXED: Count ALL articles per date, not just those with sentiment analysis
        from collections import defaultdict
        daily_data = defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0, "total": 0, "sentiment_scores": []})
        
        # First, count all articles by date
        for article in articles:
            date_str = article["published_at"][:10]  # YYYY-MM-DD
            daily_data[date_str]["total"] += 1
        
        # Then, add sentiment analysis data
        for analysis in all_analysis:
            article_id = analysis["article_id"]
            sentiment_label = analysis.get("sentiment_label", "neutral")
            sentiment_score = analysis.get("sentiment_score", 0)
            
            # Find the article to get its date
            article = next((a for a in articles if a["id"] == article_id), None)
            if article:
                date_str = article["published_at"][:10]  # YYYY-MM-DD
                daily_data[date_str]["sentiment_scores"].append(sentiment_score)
                
                if sentiment_label == "positive":
                    daily_data[date_str]["positive"] += 1
                elif sentiment_label == "negative":
                    daily_data[date_str]["negative"] += 1
                else:
                    daily_data[date_str]["neutral"] += 1
        
        # Convert to timeline format - FIXED: Aggregate all sources per date
        timeline = []
        total_articles = 0
        total_positive = 0
        total_negative = 0
        total_neutral = 0
        
        # Group by date only (aggregate all sources)
        aggregated_daily_data = defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0, "total": 0, "sentiment_scores": []})
        
        for date_str, data in daily_data.items():
            aggregated_daily_data[date_str]["total"] += data["total"]
            aggregated_daily_data[date_str]["positive"] += data["positive"]
            aggregated_daily_data[date_str]["negative"] += data["negative"]
            aggregated_daily_data[date_str]["neutral"] += data["neutral"]
            aggregated_daily_data[date_str]["sentiment_scores"].extend(data["sentiment_scores"])
        
        for date_str in sorted(aggregated_daily_data.keys()):
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
            
            timeline.append({
                "date": date_str,
                "positive": positive,
                "negative": negative,
                "neutral": neutral,
                "total": total,
                "avg_sentiment": avg_sentiment,
                "positive_pct": round((positive / total * 100) if total > 0 else 0, 1),
                "negative_pct": round((negative / total * 100) if total > 0 else 0, 1),
                "neutral_pct": round((neutral / total * 100) if total > 0 else 0, 1)
            })
        
        # Calculate summary
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
                "avg_daily_articles": avg_daily_articles
            },
            "timeline": timeline
        }
        
        # Cache the result (short TTL to keep UI fresh)
        set_cached(cache_key, result, 300)
        return result
        
    except Exception as e:
        return {"error": str(e)}

@app.get("/ml/bias_analysis_political_latest")
async def get_political_bias_latest(limit: int = 100):
    """Get latest political bias analysis results."""
    sb = get_supabase()
    try:
        result = sb.table("bias_analysis").select("*").eq("model_version", "philippine_bias_v1").eq("model_type", "political_bias").order("created_at", desc=True).limit(limit).execute()
        return result.data or []
    except Exception as e:
        return {"error": str(e)}


@app.get("/dashboard/comprehensive")
async def get_comprehensive_dashboard(period: str = "7d", source: Optional[str] = None):
    """Comprehensive dashboard data including both sentiment and political bias analysis."""
    sb = get_supabase()
    
    # Calculate date range (FIXED: Use yesterday as end date for proper day counting)
    from datetime import datetime, timedelta
    now = datetime.now()
    
    if period == "1d":
        # Last complete day (yesterday)
        start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == "7d":
        # Last 7 complete days (ending yesterday)
        start_date = (now - timedelta(days=8)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == "30d":
        # Last 30 complete days (ending yesterday)
        start_date = (now - timedelta(days=31)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        # Default to 7 complete days (ending yesterday)
        start_date = (now - timedelta(days=8)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
    
    start_date_str = start_date.isoformat()
    
    try:
        # Get articles from the period (use pagination to get ALL articles)
        articles = get_all_articles_paginated(sb, start_date_str, source)
        
        if not articles:
            return {
                "ok": True,
                "articles": {"total": 0, "by_source": {}, "by_date": {}},
                "sentiment": {"total_analyses": 0, "avg_compound": 0, "distribution": {"positive": 0, "neutral": 0, "negative": 0}},
                "political_bias": {"total_analyses": 0, "avg_bias_score": 0, "avg_confidence": 0, "distribution": {"pro_government": 0, "pro_opposition": 0, "neutral": 0, "mixed": 0}},
                "source_comparison": [],
                "timeline": [],
                "generated_at": now.isoformat()
            }
        
        # Get sentiment analysis
        article_ids = [a["id"] for a in articles]
        sentiment_result = sb.table("bias_analysis").select("*").in_("article_id", article_ids).eq("model_version", "vader_v1").eq("model_type", "sentiment").execute()
        sentiment_data = sentiment_result.data or []
        
        # Get political bias analysis
        political_result = sb.table("bias_analysis").select("*").in_("article_id", article_ids).eq("model_version", "philippine_bias_v1").eq("model_type", "political_bias").execute()
        political_data = political_result.data or []
        
        # Process sentiment data
        sentiment_scores = [s.get("sentiment_score", 0) for s in sentiment_data if s.get("sentiment_score") is not None]
        sentiment_labels = [s.get("sentiment_label", "neutral") for s in sentiment_data]
        
        sentiment_distribution = {"positive": 0, "neutral": 0, "negative": 0}
        for label in sentiment_labels:
            if label in sentiment_distribution:
                sentiment_distribution[label] += 1
        
        # Process political bias data
        political_scores = [p.get("political_bias_score", 0) for p in political_data if p.get("political_bias_score") is not None]
        political_directions = [p.get("model_metadata", {}).get("direction", "neutral") for p in political_data]
        
        political_distribution = {"pro_government": 0, "pro_opposition": 0, "neutral": 0, "mixed": 0}
        for direction in political_directions:
            if direction in political_distribution:
                political_distribution[direction] += 1
        
        # Group by source
        by_source = {}
        for article in articles:
            source_name = article.get("source", "Unknown")
            by_source[source_name] = by_source.get(source_name, 0) + 1
        
        # Group by date - FIXED: Count ALL articles per date
        by_date = {}
        for article in articles:
            date_str = article.get("published_at", "")[:10]
            if date_str:
                by_date[date_str] = by_date.get(date_str, 0) + 1
        
        # Create timeline
        timeline = []
        for date_str in sorted(by_date.keys()):
            day_articles = [a for a in articles if a.get("published_at", "").startswith(date_str)]
            day_article_ids = [a["id"] for a in day_articles]
            
            day_sentiment = [s for s in sentiment_data if s.get("article_id") in day_article_ids]
            day_political = [p for p in political_data if p.get("article_id") in day_article_ids]
            
            day_sentiment_scores = [s.get("sentiment_score", 0) for s in day_sentiment if s.get("sentiment_score") is not None]
            day_political_scores = [p.get("political_bias_score", 0) for p in day_political if p.get("political_bias_score") is not None]
            day_political_confidences = [p.get("confidence_score", 0) for p in day_political if p.get("confidence_score") is not None]
            
            timeline.append({
                "date": date_str,
                "articles": len(day_articles),
                "sentiment": {
                    "avg_score": sum(day_sentiment_scores) / len(day_sentiment_scores) if day_sentiment_scores else 0,
                    "distribution": {
                        "positive": len([s for s in day_sentiment if s.get("sentiment_label") == "positive"]),
                        "neutral": len([s for s in day_sentiment if s.get("sentiment_label") == "neutral"]),
                        "negative": len([s for s in day_sentiment if s.get("sentiment_label") == "negative"])
                    }
                },
                "political_bias": {
                    "avg_bias_score": sum(day_political_scores) / len(day_political_scores) if day_political_scores else 0,
                    "avg_confidence": sum(day_political_confidences) / len(day_political_confidences) if day_political_confidences else 0,
                    "distribution": {
                        "pro_government": len([p for p in day_political if p.get("model_metadata", {}).get("direction") == "pro_government"]),
                        "pro_opposition": len([p for p in day_political if p.get("model_metadata", {}).get("direction") == "pro_opposition"]),
                        "neutral": len([p for p in day_political if p.get("model_metadata", {}).get("direction") == "neutral"])
                    }
                }
            })
        
        # Source comparison
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
            
            source_comparison.append({
                "source": source_name,
                "article_count": count,
                "political_bias": {
                    "avg_bias_score": sum(source_political_scores) / len(source_political_scores) if source_political_scores else 0,
                    "avg_confidence": sum(source_political_confidences) / len(source_political_confidences) if source_political_confidences else 0,
                    "distribution": source_political_distribution
                }
            })
        
        return {
            "ok": True,
            "articles": {
                "total": len(articles),
                "by_source": by_source,
                "by_date": by_date
            },
            "sentiment": {
                "total_analyses": len(sentiment_data),
                "avg_compound": sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0,
                "distribution": sentiment_distribution
            },
            "political_bias": {
                "total_analyses": len(political_data),
                "avg_bias_score": sum(political_scores) / len(political_scores) if political_scores else 0,
                "avg_confidence": sum([p.get("confidence_score", 0) for p in political_data if p.get("confidence_score") is not None]) / len([p for p in political_data if p.get("confidence_score") is not None]) if political_data else 0,
                "distribution": political_distribution
            },
            "source_comparison": source_comparison,
            "timeline": timeline,
            "generated_at": now.isoformat()
        }
        
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/bias/summary")
async def bias_summary(days: int = Query(default=30, ge=1, le=180)):
    """OPTIMIZED: Get political bias summary with trends-style caching"""
    cache_key = f"bias_summary:{days}"
    
    # Try cache first (like trends)
    cached_data = get_cached(cache_key)
    if cached_data:
        return cached_data
    
    sb = get_supabase()
    try:
        # Calculate date range
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        # OPTIMIZED: Single query with JOIN instead of N+1
        # SENIOR APPROACH: Use pagination function like trends endpoint
        
        all_analysis = get_all_bias_analysis_paginated(sb, start_date, "political_bias")
        
        if not all_analysis:
            empty_response = {"ok": True, "daily_buckets": [], "distribution": {}, "top_sources": [], "top_categories": [], "recent_examples": []}
            # Cache empty result for 1 minute (like trends)
            set_cached(cache_key, empty_response, 60)
            return empty_response
        
        # Calculate distribution
        distribution = {}
        for item in all_analysis:
            direction = item.get("model_metadata", {}).get("direction", "unknown")
            distribution[direction] = distribution.get(direction, 0) + 1
        
        # Calculate daily buckets
        daily_buckets = {}
        for item in all_analysis:
            date = item.get("created_at", "")[:10]
            if date not in daily_buckets:
                daily_buckets[date] = {"total": 0, "by_direction": {}}
            
            direction = item.get("model_metadata", {}).get("direction", "unknown")
            daily_buckets[date]["total"] += 1
            daily_buckets[date]["by_direction"][direction] = daily_buckets[date]["by_direction"].get(direction, 0) + 1
        
        # Convert to list format
        daily_buckets_list = []
        for date in sorted(daily_buckets.keys(), reverse=True):
            data = daily_buckets[date]
            daily_buckets_list.append({
                "date": date,
                "total": data["total"],
                "by_direction": data["by_direction"]
            })
        
        # Calculate top sources from articles
        source_counts = {}
        for item in all_analysis:
            article = item.get("articles", {})
            source = article.get("source", "Unknown")
            source_counts[source] = source_counts.get(source, 0) + 1
        
        top_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Calculate top categories from articles
        category_counts = {}
        for item in all_analysis:
            article = item.get("articles", {})
            category = article.get("category", "Unknown")
            if category:
                category_counts[category] = category_counts.get(category, 0) + 1
        
        top_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Get recent examples
        recent_examples = []
        for item in all_analysis[:5]:
            article = item.get("articles", {})
            recent_examples.append({
                "id": article.get("id", 0),
                "title": article.get("title", ""),
                "source": article.get("source", "Unknown"),
                "published_at": article.get("published_at", "")
            })
        
        response = {
            "ok": True,
            "daily_buckets": daily_buckets_list,
            "distribution": distribution,
            "top_sources": [{"source": k, "count": v} for k, v in top_sources],
            "top_categories": [{"category": k, "count": v} for k, v in top_categories],
            "recent_examples": recent_examples
        }
        
        # Cache for 5 minutes (like trends)
        set_cached(cache_key, response, 300)
        return response
        
    except Exception as e:
        return {"ok": False, "error": str(e), "daily_buckets": [], "distribution": {}, "top_sources": [], "top_categories": [], "recent_examples": []}

@app.get("/bias/explain/{article_id}")
async def bias_explain(article_id: int):
    """Return detailed bias analysis (latest) for a specific article, with keyword matches and components."""
    sb = get_supabase()
    try:
        result = sb.table("bias_analysis").select("*, articles(*)").eq("article_id", article_id).eq("model_type", "political_bias").order("created_at", desc=True).limit(1).execute()
        rows = result.data or []
        if not rows:
            return {"ok": False, "error": "No political_bias analysis found for article"}
        row = rows[0]
        md = row.get("model_metadata") or {}
        return {
            "ok": True,
            "article": row.get("articles", {}),
            "direction": md.get("direction"),
            "keyword_matches": md.get("keyword_matches", {}),
            "analysis_components": md.get("analysis_components", {}),
            "political_bias_score": row.get("political_bias_score"),
            "confidence_score": row.get("confidence_score"),
            "created_at": row.get("created_at")
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/bias/source_summary")
async def bias_source_summary(days: int = Query(default=30, ge=1, le=180)):
    """Return per-source distribution of political_bias directions within the time window."""
    sb = get_supabase()
    try:
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        all_analysis = get_all_bias_analysis_paginated(sb, start_date, "political_bias")
        if not all_analysis:
            return {"ok": True, "by_source": {}}
        by_source = {}
        for item in all_analysis:
            article = item.get("articles", {})
            source = article.get("source", "Unknown")
            direction = item.get("model_metadata", {}).get("direction", "unknown")
            if source not in by_source:
                by_source[source] = {}
            by_source[source][direction] = by_source[source].get(direction, 0) + 1
        return {"ok": True, "by_source": by_source}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/cache/stats")
async def get_cache_stats():
    """Get Redis cache statistics"""
    try:
        from app.cache import cache
        info = cache.redis_client.info()
        return {
            "ok": True,
            "stats": {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "total_commands_processed": info.get("total_commands_processed", 0)
            }
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/cache/clear")
async def clear_cache():
    """Clear all cache"""
    try:
        from app.cache import clear_cache
        cleared = clear_cache()
        return {"ok": True, "cleared_keys": cleared}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/cache/keys")
async def list_cache_keys():
    """List all cache keys"""
    try:
        from app.cache import cache
        keys = cache.redis_client.keys("*")
        return {"ok": True, "keys": keys, "count": len(keys)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/maintenance/backfill_is_funds")
async def backfill_is_funds(x_admin_token: Optional[str] = Header(default=None)):
    if ADMIN_TOKEN and x_admin_token != ADMIN_TOKEN:
        return {"ok": False, "error": "unauthorized"}
    try:
        backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        script_path = os.path.join(backend_root, 'scripts', 'backfill_is_funds.py')
        if not os.path.exists(script_path):
            return {"ok": False, "error": f"Script not found: {script_path}"}
        # Prefer running as a module so package imports work reliably in Docker
        env = os.environ.copy()
        # Ensure backend root is on PYTHONPATH so 'scripts' is importable as a top-level package
        env["PYTHONPATH"] = backend_root + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        # Run as module to keep consistent imports in Docker container
        proc = Popen([sys.executable, "-m", "scripts.backfill_is_funds"], cwd=backend_root, stdout=PIPE, stderr=PIPE, env=env)
        # Return immediately; let it run in background to avoid blocking the request
        return {"ok": True, "pid": proc.pid, "started": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/maintenance/recompute_is_funds")
async def recompute_is_funds(x_admin_token: Optional[str] = Header(default=None)):
    if ADMIN_TOKEN and x_admin_token != ADMIN_TOKEN:
        return {"ok": False, "error": "unauthorized"}
    try:
        backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        env = os.environ.copy()
        env["PYTHONPATH"] = backend_root + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        proc = Popen([sys.executable, "-m", "scripts.recompute_is_funds"], cwd=backend_root, stdout=PIPE, stderr=PIPE, env=env)
        return {"ok": True, "pid": proc.pid, "started": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/maintenance/cleanup_funds_sync")
async def cleanup_funds_sync(limit: int = 100, x_admin_token: Optional[str] = Header(default=None)):
    """Synchronously clean up funds classifications for testing"""
    if ADMIN_TOKEN and x_admin_token != ADMIN_TOKEN:
        return {"ok": False, "error": "unauthorized"}
    
    try:
        from app.pipeline.store import classify_is_funds
        sb = get_supabase()
        
        # Get a limited batch for testing
        res = sb.table("articles").select("id,title,content,is_funds").eq("is_funds", True).limit(limit).execute()
        articles = res.data or []
        
        to_false = []
        for article in articles:
            want_true = classify_is_funds(article.get("title"), article.get("content"))
            if not want_true:
                to_false.append(article["id"])
        
        # Update to false
        if to_false:
            sb.table("articles").update({"is_funds": False}).in_("id", to_false).execute()
        
        return {
            "ok": True,
            "checked": len(articles),
            "removed_from_funds": len(to_false),
            "removed_ids": to_false
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/maintenance/fix_specific_articles")
async def fix_specific_articles(article_ids: list[int], x_admin_token: Optional[str] = Header(default=None)):
    """Fix specific articles by setting is_funds to false"""
    if ADMIN_TOKEN and x_admin_token != ADMIN_TOKEN:
        return {"ok": False, "error": "unauthorized"}
    
    try:
        sb = get_supabase()
        
        # Update articles to is_funds = false
        result = sb.table("articles").update({"is_funds": False}).in_("id", article_ids).execute()
        
        return {
            "ok": True,
            "updated_count": len(result.data or []),
            "article_ids": article_ids
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/analytics/funds/extract")
async def extract_funds_analytics(article_ids: list[int], x_admin_token: Optional[str] = Header(default=None)):
    """Extract detailed analytics from funds articles"""
    if ADMIN_TOKEN and x_admin_token != ADMIN_TOKEN:
        return {"ok": False, "error": "unauthorized"}
    
    try:
        from app.analytics.funds_analytics import extract_funds_analytics
        sb = get_supabase()
        
        # Get articles
        res = sb.table("articles").select("id,title,content,published_at").in_("id", article_ids).execute()
        articles = res.data or []
        
        analytics_results = []
        for article in articles:
            analytics = extract_funds_analytics(
                article_id=article["id"],
                title=article.get("title", ""),
                content=article.get("content", ""),
                published_at=article.get("published_at", "")
            )
            analytics_results.append({
                "article_id": analytics.article_id,
                "agencies": [{"text": a.text, "confidence": a.confidence} for a in analytics.agencies],
                "amounts": [{"text": a.text, "confidence": a.confidence} for a in analytics.amounts],
                "locations": [{"text": a.text, "confidence": a.confidence} for a in analytics.locations],
                "people": [{"text": a.text, "confidence": a.confidence} for a in analytics.people],
                "total_amount": analytics.total_amount,
                "primary_agency": analytics.primary_agency,
                "project_types": analytics.project_types,
                "corruption_indicators": analytics.corruption_indicators,
                "extraction_confidence": analytics.extraction_confidence,
                "funds_relevance_score": analytics.funds_relevance_score
            })
        
        return {
            "ok": True,
            "analytics": analytics_results,
            "total_processed": len(analytics_results)
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/analytics/funds/trends")
async def get_funds_trends(days_back: int = 30, source: Optional[str] = None):
    """Get comprehensive funds trends and analytics"""
    try:
        from app.analytics.funds_analytics import extract_funds_analytics, analyze_funds_trends
        sb = get_supabase()
        
        # Calculate date range
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Build query
        query = sb.table("articles").select("id,title,content,published_at").eq("is_funds", True)
        
        if source:
            query = query.eq("source", source)
        
        # Get articles
        res = query.gte("published_at", start_date.isoformat()).lte("published_at", end_date.isoformat()).execute()
        articles = res.data or []
        
        # Extract analytics for all articles
        analytics_list = []
        for article in articles:
            analytics = extract_funds_analytics(
                article_id=article["id"],
                title=article.get("title", ""),
                content=article.get("content", ""),
                published_at=article.get("published_at", "")
            )
            analytics_list.append(analytics)
        
        # Analyze trends
        trends = analyze_funds_trends(analytics_list)
        
        return {
            "ok": True,
            "period": f"{days_back} days",
            "source": source or "all",
            "trends": trends,
            "articles_analyzed": len(analytics_list)
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/ml/funds/insights")
async def get_funds_insights(days_back: int = 30, source: Optional[str] = None):
    """Get comprehensive funds analytics and insights"""
    sb = get_supabase()
    
    try:
        # Calculate date range
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Get funds articles
        query = sb.table("articles").select("*").eq("is_funds", True).gte("published_at", start_date.isoformat())
        if source:
            query = query.eq("source", source)
        
        result = query.execute()
        articles = result.data or []
        
        if not articles:
            return {
                "ok": True,
                "insights": {
                    "summary": {"total_articles": 0},
                    "entities": {},
                    "trends": {}
                },
                "articles_analyzed": 0
            }
        
        # Extract insights using the same logic as the Celery task
        from app.workers.ml_tasks import _extract_funds_insights
        insights = _extract_funds_insights(articles)
        
        return {
            "ok": True,
            "insights": insights,
            "articles_analyzed": len(articles),
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.post("/ml/funds/analyze")
async def trigger_funds_analysis(days_back: int = 30):
    """Trigger background funds analysis task"""
    try:
        from app.workers.ml_tasks import analyze_funds_insights_task
        task = analyze_funds_insights_task.delay(days_back)
        return {"message": "Funds analysis started", "task_id": task.id}
    except Exception as e:
        return {"error": str(e)}

@app.get("/ml/funds/classify")
async def classify_funds_text(title: str, content: str = ""):
    """Test funds classification with spaCy and regex"""
    try:
        from app.pipeline.store import classify_is_funds, _spacy_funds_analysis
        import os
        
        # Get both regex and spaCy results
        text = f"{title}\n{content}"
        regex_result = classify_is_funds(title, content)
        
        spacy_result = None
        if os.getenv("USE_SPACY_FUNDS", "false").lower() == "true":
            spacy_result = _spacy_funds_analysis(text)
        
        return {
            "ok": True,
            "text": text[:200] + "..." if len(text) > 200 else text,
            "regex_result": regex_result,
            "spacy_result": spacy_result,
            "final_result": regex_result
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/ml/funds/eval")
async def eval_funds_classifier(
    sample_size: int = 200,
    days_back: int = 30,
    source: Optional[str] = None,
    spacy_confidence_confirm: float = 0.6,
    spacy_confidence_veto: float = 0.5,
    only_candidates: bool = False
):
    """Compare regex vs spaCy decisions on a recent sample with configurable thresholds.
    Returns agreement metrics, confusion breakdowns, and top-entity evidence for disagreements.
    """
    try:
        from app.core.supabase import get_supabase
        from app.pipeline.store import classify_is_funds as classify_regex
        from app.pipeline.store import _spacy_funds_analysis
        import os
        now = datetime.now()
        start = now - timedelta(days=days_back)

        sb = get_supabase()
        query = (
            sb.table("articles")
            .select("id,title,content,published_at,source")
            .gte("published_at", start.isoformat())
            .lte("published_at", now.isoformat())
            .order("published_at", desc=True)
            .limit(sample_size)
        )
        if source:
            query = query.eq("source", source)
        res = query.execute()
        articles = res.data or []

        use_spacy = os.getenv("USE_SPACY_FUNDS", "false").lower() == "true"

        total = len(articles)
        agree = 0
        disagree = 0
        disagreements = []
        # Confusion-style counts
        # regex_decision vs spacy_raw (ungated) and vs final_spacy_decision (gated)
        confusion_raw = {"regex_true_spacy_true": 0, "regex_true_spacy_false": 0, "regex_false_spacy_true": 0, "regex_false_spacy_false": 0}
        confusion_final = {"regex_true_spacy_true": 0, "regex_true_spacy_false": 0, "regex_false_spacy_true": 0, "regex_false_spacy_false": 0}

        for a in articles:
            title = (a.get("title") or "")
            content = (a.get("content") or "")
            text = f"{title}\n{content}"

            regex_decision = classify_regex(title, content)
            spacy_info = _spacy_funds_analysis(text) if use_spacy else {"is_funds": None, "confidence": 0.0, "entities": []}

            # If only_candidates is set, skip items that are unlikely funds to focus evaluation
            if only_candidates:
                has_money_token = any(tok in text.lower() for tok in [
                    "budget","allocation","appropriation","disbursement","fund","funds","billion","million","trillion","peso","pesos","php","₱","php "
                ])
                ents = spacy_info.get("entities") or {}
                has_spacy_money = bool((ents.get("money") or []))
                # Consider gov org cues from NER
                gov_org_cues = {"dpwh","dbm","coa","comelec","dilg","doh","deped","dotr","senate","house","congress","lgu","barangay","province","city","municipality","malacañang","palace","ombudsman","commission on audit","department of budget and management","department of public works and highways","department of health","department of education","department of transportation"}
                orgs_lower = {o.lower() for o in (ents.get("orgs") or [])}
                has_gov_org = any(term in orgs_lower for term in gov_org_cues)
                spacy_raw_bool_tmp = None if spacy_info.get("is_funds") is None else bool(spacy_info.get("is_funds"))
                if (not regex_decision) and (not has_money_token) and (not has_spacy_money) and (not has_gov_org) and (spacy_raw_bool_tmp is not True):
                    continue

            spacy_raw_bool = None if spacy_info.get("is_funds") is None else bool(spacy_info.get("is_funds"))
            if spacy_raw_bool is True and regex_decision is True:
                confusion_raw["regex_true_spacy_true"] += 1
            elif spacy_raw_bool is False and regex_decision is True:
                confusion_raw["regex_true_spacy_false"] += 1
            elif spacy_raw_bool is True and regex_decision is False:
                confusion_raw["regex_false_spacy_true"] += 1
            elif spacy_raw_bool is False and regex_decision is False:
                confusion_raw["regex_false_spacy_false"] += 1

            final_spacy_decision = regex_decision
            if spacy_info.get("is_funds") is not None:
                if spacy_info.get("confidence", 0.0) > spacy_confidence_confirm:
                    final_spacy_decision = bool(spacy_info["is_funds"])
                elif regex_decision and spacy_info.get("confidence", 0.0) < spacy_confidence_veto:
                    final_spacy_decision = False

            # Confusion for gated decision
            if final_spacy_decision and regex_decision:
                confusion_final["regex_true_spacy_true"] += 1
            elif (not final_spacy_decision) and regex_decision:
                confusion_final["regex_true_spacy_false"] += 1
            elif final_spacy_decision and (not regex_decision):
                confusion_final["regex_false_spacy_true"] += 1
            else:
                confusion_final["regex_false_spacy_false"] += 1

            if regex_decision == final_spacy_decision:
                agree += 1
            else:
                disagree += 1
                if len(disagreements) < 25:
                    # Pull light-weight entity evidence for inspection
                    ents = spacy_info.get("entities") or {}
                    disagreements.append({
                        "id": a.get("id"),
                        "source": a.get("source"),
                        "published_at": a.get("published_at"),
                        "title": title[:160],
                        "regex": regex_decision,
                        "spacy": final_spacy_decision,
                        "spacy_confidence": spacy_info.get("confidence"),
                        "evidence": {
                            "orgs": ents.get("orgs", [])[:5],
                            "money": ents.get("money", [])[:5],
                            "gpes": ents.get("gpes", [])[:5],
                            "laws": ents.get("laws", [])[:5],
                        }
                    })

        return {
            "ok": True,
            "config": {"use_spacy": use_spacy, "sample_size": total, "days_back": days_back, "source": source or "all", "confirm": spacy_confidence_confirm, "veto": spacy_confidence_veto, "only_candidates": only_candidates},
            "metrics": {
                "agreement": agree,
                "disagreement": disagree,
                "agreement_rate": (agree / total) if total else 0.0,
                "confusion_raw": confusion_raw,
                "confusion_final": confusion_final,
            },
            "examples": disagreements,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/bias/articles")
async def bias_articles(direction: Optional[str] = Query(default=None), limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
    sb = get_supabase()
    try:
        # Get articles with political bias analysis
        query = sb.table("bias_analysis").select("*, articles(*)").eq("model_type", "political_bias").order("created_at", desc=True).range(offset, offset + limit - 1)
        
        if direction:
            query = query.eq("model_metadata->direction", direction)
        
        result = query.execute()
        
        return {"ok": True, "items": result.data or [], "total": len(result.data or [])}
        
    except Exception as e:
        return {"ok": False, "error": str(e), "items": [], "total": 0}