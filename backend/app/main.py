from fastapi import FastAPI, Body
from .core.config import settings
from app.workers.tasks import scrape_inquirer_task, scrape_abs_cbn_task, scrape_gma_task, scrape_philstar_task, scrape_manila_bulletin_task, scrape_rappler_task, scrape_sunstar_task, scrape_manila_times_task
from app.workers.celery_app import celery
from celery.result import AsyncResult
from typing import Optional
from app.core.supabase import get_supabase
from app.workers.ml_tasks import analyze_articles_task
from fastapi.middleware.cors import CORSMiddleware

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
async def get_trends(period: str = "7d", source: Optional[str] = None):
    sb = get_supabase()
    
    # Calculate date range
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
        # Get articles from the period
        query = sb.table("articles").select("*").gte("published_at", start_date_str).order("published_at", desc=True)
        
        if source:
            query = query.eq("source", source)
        
        articles_result = query.limit(1000).execute()
        articles = articles_result.data or []
        
        if not articles:
            return {
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
        
        # Get analysis for these articles
        article_ids = [a["id"] for a in articles]
        analysis_result = sb.table("bias_analysis").select("*").in_("article_id", article_ids).eq("model_version", "vader_v1").eq("model_type", "sentiment").execute()
        analysis_data = analysis_result.data or []
        
        # Group by date
        from collections import defaultdict
        daily_data = defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0, "total": 0, "sentiment_scores": []})
        
        for analysis in analysis_data:
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
        
        return {
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
        
    except Exception as e:
        return {"error": str(e)}
