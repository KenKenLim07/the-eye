from celery import shared_task
from app.core.supabase import get_supabase
from app.ml.bias import build_comprehensive_bias_analysis
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any

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
            text = " ".join([str(r.get("title") or ""), str(r.get("content") or "")] ).strip()
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

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def analyze_funds_insights_task(self, days_back: int = 30):
    """Generate comprehensive funds analytics and insights"""
    sb = get_supabase()
    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Get funds-related articles
        funds_query = sb.table("articles").select("*").eq("is_funds", True).gte("published_at", start_date.isoformat()).lte("published_at", end_date.isoformat())
        funds_result = funds_query.execute()
        funds_articles = funds_result.data or []
        
        if not funds_articles:
            return {"ok": True, "insights": {}, "articles_analyzed": 0}
        
        # Extract insights
        insights = _extract_funds_insights(funds_articles)
        
        # Store insights (you could create a funds_insights table)
        logger.info(f"Generated funds insights for {len(funds_articles)} articles")
        
        return {
            "ok": True, 
            "insights": insights, 
            "articles_analyzed": len(funds_articles),
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Funds insights analysis failed: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30 * (2 ** self.request.retries))
        return {"ok": False, "error": str(e), "articles_analyzed": 0}

def _extract_funds_insights(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract meaningful insights from funds articles"""
    insights = {
        "summary": {
            "total_articles": len(articles),
            "top_sources": {},
            "top_categories": {},
            "date_distribution": {}
        },
        "entities": {
            "government_agencies": {},
            "corruption_keywords": {},
            "money_amounts": []
        },
        "trends": {
            "daily_counts": {},
            "source_sentiment": {}
        }
    }
    
    # Government agencies and corruption keywords
    gov_agencies = ["dpwh", "dbm", "coa", "comelec", "dilg", "doh", "deped", "dotr", "senate", "house", "congress"]
    corruption_terms = ["pork", "kickback", "anomaly", "graft", "plunder", "misuse", "overprice", "scam", "whistleblower"]
    
    for article in articles:
        # Source and category analysis
        source = article.get("source", "unknown")
        category = article.get("category", "unknown")
        
        insights["summary"]["top_sources"][source] = insights["summary"]["top_sources"].get(source, 0) + 1
        insights["summary"]["top_categories"][category] = insights["summary"]["top_categories"].get(category, 0) + 1
        
        # Date distribution
        published_at = article.get("published_at", "")
        if published_at:
            date_key = published_at[:10]  # YYYY-MM-DD
            insights["summary"]["date_distribution"][date_key] = insights["summary"]["date_distribution"].get(date_key, 0) + 1
        
        # Entity extraction from title and content
        text = f"{article.get('title', '')} {article.get('content', '')}".lower()
        
        # Count government agencies mentioned
        for agency in gov_agencies:
            if agency in text:
                insights["entities"]["government_agencies"][agency] = insights["entities"]["government_agencies"].get(agency, 0) + 1
        
        # Count corruption keywords
        for term in corruption_terms:
            if term in text:
                insights["entities"]["corruption_keywords"][term] = insights["entities"]["corruption_keywords"].get(term, 0) + 1
        
        # Extract money amounts (simple regex)
        import re
        money_pattern = r'(\d+(?:\.\d+)?)\s*(?:billion|million|b|m|php|peso|pesos)'
        money_matches = re.findall(money_pattern, text)
        for amount in money_matches:
            insights["entities"]["money_amounts"].append(float(amount))
    
    # Sort and limit top results
    insights["summary"]["top_sources"] = dict(sorted(insights["summary"]["top_sources"].items(), key=lambda x: x[1], reverse=True)[:10])
    insights["summary"]["top_categories"] = dict(sorted(insights["summary"]["top_categories"].items(), key=lambda x: x[1], reverse=True)[:10])
    insights["entities"]["government_agencies"] = dict(sorted(insights["entities"]["government_agencies"].items(), key=lambda x: x[1], reverse=True)[:10])
    insights["entities"]["corruption_keywords"] = dict(sorted(insights["entities"]["corruption_keywords"].items(), key=lambda x: x[1], reverse=True)[:10])
    
    # Calculate money statistics
    if insights["entities"]["money_amounts"]:
        amounts = insights["entities"]["money_amounts"]
        insights["entities"]["money_stats"] = {
            "total_amounts": len(amounts),
            "max_amount": max(amounts),
            "min_amount": min(amounts),
            "avg_amount": sum(amounts) / len(amounts)
        }
    
    return insights
