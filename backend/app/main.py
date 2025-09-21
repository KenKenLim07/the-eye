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
async def get_articles(limit: int = 50, offset: int = 0, source: Optional[str] = None, category: Optional[str] = None):
    sb = get_supabase()
    
    query = sb.table("articles").select("*")
    
    if source:
        query = query.eq("source", source)
    if category:
        query = query.eq("category", category)
    
    query = query.order("published_at", desc=True).range(offset, offset + limit - 1)
    
    try:
        result = query.execute()
        return {"articles": result.data, "count": len(result.data)}
    except Exception as e:
        return {"error": str(e), "articles": []}

@app.get("/articles/home-optimized")
async def get_home_articles(limit_per_source: int = 10):
    """Optimized endpoint for home page - single query instead of 7 separate ones"""
    # Generate cache key
    cache_key = f"home_articles:{limit_per_source}"
    
    # Check cache first
    cached_result = get_cached(cache_key)
    if cached_result:
        return cached_result
    
    sb = get_supabase()
    
    try:
        # Single query to get latest articles from all sources
        result = sb.table("articles").select("*").order("published_at", desc=True).limit(70).execute()
        
        if not result.data:
            empty_result = {"articles_by_source": {}}
            # Cache empty result for 1 minute
            set_cached(cache_key, empty_result, 60)
            return empty_result
        
        # Group by source
        articles_by_source = {}
        for article in result.data:
            source = article.get("source", "Unknown")
            if source not in articles_by_source:
                articles_by_source[source] = []
            if len(articles_by_source[source]) < limit_per_source:
                articles_by_source[source].append(article)
        
        result_data = {"articles_by_source": articles_by_source}
        
        # Cache the result for 2 minutes (home page changes more frequently)
        set_cached(cache_key, result_data, 600)
        return result_data
        
    except Exception as e:
        return {"error": str(e), "articles_by_source": {}}@app.get("/articles/{article_id}")
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
async def get_trends(period: str = "7d", source: Optional[str] = None):
    # Generate cache key
    cache_key = f"trends:{period}:{source or 'all'}"
    
    # Check cache first
    cached_result = get_cached(cache_key)
    if cached_result:
        return cached_result
    
    sb = get_supabase()
    
    # Calculate date range (SIMPLE VERSION)
    from datetime import datetime, timedelta
    now = datetime.now()
    
    if period == "1d":
        start_date = now - timedelta(days=1)
    elif period == "7d":
        start_date = now - timedelta(days=7)
    elif period == "30d":
        start_date = now - timedelta(days=30)
    else:
        start_date = now - timedelta(days=7)
    
    start_date_str = start_date.isoformat()
    
    try:
        # Get articles from the period (with pagination)
        articles = get_all_articles_paginated(sb, start_date_str, source)
        
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
        
        # Group by date
        from collections import defaultdict
        daily_data = defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0, "total": 0, "sentiment_scores": []})
        
        for analysis in all_analysis:
            article_id = analysis["article_id"]
            sentiment_label = analysis.get("sentiment_label", "neutral")
            sentiment_score = analysis.get("sentiment_score", 0)
            
            # Find the article to get its date
            article = next((a for a in articles if a["id"] == article_id), None)
            if article:
                date_str = article["published_at"][:10]  # YYYY-MM-DD
                daily_data[date_str]["total"] += 1
                daily_data[date_str]["sentiment_scores"].append(sentiment_score)
                
                if sentiment_label == "positive":
                    daily_data[date_str]["positive"] += 1
                elif sentiment_label == "negative":
                    daily_data[date_str]["negative"] += 1
                else:
                    daily_data[date_str]["neutral"] += 1
        
        # Convert to timeline format
        timeline = []
        total_articles = 0
        total_positive = 0
        total_negative = 0
        total_neutral = 0
        
        for date_str in sorted(daily_data.keys()):
            data = daily_data[date_str]
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
        
        # Cache the result for 5 minutes
        set_cached(cache_key, result, 1800)
        return result
        
    except Exception as e:
        return {"error": str(e)}@app.get("/ml/bias_analysis_political_latest")
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
        # Get articles from the period
        query = sb.table("articles").select("*").gte("published_at", start_date_str).order("published_at", desc=True)
        
        if source:
            query = query.eq("source", source)
        
        articles_result = query.limit(1000).execute()
        articles = articles_result.data or []
        
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
        
        # Group by date
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