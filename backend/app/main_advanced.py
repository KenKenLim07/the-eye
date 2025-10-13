#!/usr/bin/env python3
"""
Advanced Sentiment Analysis API Endpoints
Thesis-worthy endpoints for revolutionary sentiment research
"""
from fastapi import FastAPI, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import json
from app.core.supabase import get_supabase
from app.analytics.advanced_sentiment import AdvancedSentimentAnalyzer
from app.nlp.spacy_nlp import extract_entities, extract_keyphrases
from app.cache import get_cached, set_cached

# Initialize the advanced analyzer
analyzer = AdvancedSentimentAnalyzer()

def get_advanced_sentiment_data(sb, start_date: str, end_date: str = None, source: str = None) -> List[Dict]:
    """Get sentiment data for advanced analysis - uses same pagination as trends"""
    try:
        # Import the same pagination function used by trends
        from app.main import get_all_articles_paginated
        
        # Get ALL articles from the period (same as trends endpoint)
        articles = get_all_articles_paginated(sb, start_date, source, end_date)
        
        if not articles:
            return []
        
        # Get sentiment analysis for these articles
        article_ids = [a["id"] for a in articles]
        all_analysis = []
        batch_size = 500
        
        for i in range(0, len(article_ids), batch_size):
            batch_ids = article_ids[i:i + batch_size]
            analysis_result = sb.table("bias_analysis").select("*").in_("article_id", batch_ids).eq("model_type", "sentiment").execute()
            all_analysis.extend(analysis_result.data or [])
        
        # Group by date and source
        from collections import defaultdict
        daily_data = defaultdict(lambda: defaultdict(lambda: {"positive": 0, "negative": 0, "neutral": 0, "total": 0}))
        
        # Count all articles by date and source
        for article in articles:
            date_str = article["published_at"][:10]  # YYYY-MM-DD
            source_name = article.get("source", "unknown")
            daily_data[date_str][source_name]["total"] += 1
        
        # Add sentiment analysis data
        for analysis in all_analysis:
            article_id = analysis["article_id"]
            sentiment_label = analysis.get("sentiment_label", "neutral")
            
            # Find the article to get its date and source
            article = next((a for a in articles if a["id"] == article_id), None)
            if article:
                date_str = article["published_at"][:10]
                source_name = article.get("source", "unknown")
                
                if sentiment_label == "positive":
                    daily_data[date_str][source_name]["positive"] += 1
                elif sentiment_label == "negative":
                    daily_data[date_str][source_name]["negative"] += 1
                else:
                    daily_data[date_str][source_name]["neutral"] += 1
        
        # Convert to list format
        result = []
        for date_str, sources in daily_data.items():
            for source_name, data in sources.items():
                result.append({
                    "date": date_str,
                    "source": source_name,
                    "positive": data["positive"],
                    "negative": data["negative"],
                    "neutral": data["neutral"],
                    "total": data["total"]
                })
        
        return result
        
    except Exception as e:
        print(f"Error getting advanced sentiment data: {e}")
        return []

# Advanced API endpoints
async def get_sentiment_predictions(period: str = "30d", source: Optional[str] = None):
    """
    Revolutionary: Predict future sentiment trends
    First predictive model for Philippine news sentiment
    """
    cache_key = f"sentiment_predictions:{period}:{source or 'all'}"
    
    # Check cache first
    cached_result = get_cached(cache_key)
    if cached_result:
        return cached_result
    
    sb = get_supabase()
    
    # Calculate date range
    now = datetime.now()
    if period == "7d":
        start_date = now - timedelta(days=7)
    elif period == "30d":
        start_date = now - timedelta(days=30)
    elif period == "90d":
        start_date = now - timedelta(days=90)
    else:
        start_date = now - timedelta(days=30)
    
    start_date_str = start_date.isoformat()
    
    try:
        # Get historical data
        historical_data = get_advanced_sentiment_data(sb, start_date_str, source=source)
        
        if not historical_data:
            return {
                "ok": False,
                "error": "No data available for prediction",
                "prediction": None
            }
        
        # Generate prediction
        prediction = analyzer.predict_sentiment_trends(historical_data, days_ahead=7)
        
        result = {
            "ok": True,
            "prediction": {
                "predicted_sentiment": prediction.predicted_sentiment,
                "confidence_interval": prediction.confidence_interval,
                "prediction_accuracy": prediction.prediction_accuracy,
                "trend_direction": prediction.trend_direction,
                "next_week_forecast": prediction.next_week_forecast,
                "key_factors": prediction.key_factors
            },
            "historical_data_points": len(historical_data),
            "generated_at": datetime.now().isoformat()
        }
        
        # Cache for 1 hour
        set_cached(cache_key, result, 3600)
        return result
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "prediction": None
        }

async def get_source_bias_analysis(period: str = "30d"):
    """
    Revolutionary: Comprehensive bias analysis for all sources
    Objective bias quantification without subjective interpretation
    """
    cache_key = f"source_bias_analysis:{period}"
    
    # Check cache first - TEMPORARILY DISABLED FOR DEBUGGING
    # cached_result = get_cached(cache_key)
    # if cached_result:
    #     return cached_result
    
    sb = get_supabase()
    
    # Calculate date range
    now = datetime.now()
    if period == "7d":
        start_date = now - timedelta(days=7)
    elif period == "30d":
        start_date = now - timedelta(days=30)
    elif period == "90d":
        start_date = now - timedelta(days=90)
    else:
        start_date = now - timedelta(days=30)
    
    start_date_str = start_date.isoformat()
    
    try:
        # Get all data
        all_data = get_advanced_sentiment_data(sb, start_date_str)
        
        if not all_data:
            return {
                "ok": False,
                "error": "No data available for bias analysis",
                "sources": []
            }
        
        # Group by source
        from collections import defaultdict
        source_data = defaultdict(list)
        for item in all_data:
            source_data[item["source"]].append(item)
        
        # Analyze each source
        source_analyses = []
        for source, data in source_data.items():
            analysis = analyzer.analyze_source_bias(data, all_data)
            source_analyses.append({
                "source": analysis.source,
                "overall_sentiment_bias": analysis.overall_sentiment_bias,
                "political_bias_score": analysis.political_bias_score,
                "topic_sentiment_map": analysis.topic_sentiment_map,
                "temporal_consistency": analysis.temporal_consistency,
                "influence_score": analysis.influence_score,
                "editorial_positioning": analysis.editorial_positioning,
                "articles_analyzed": len(data)
            })
        
        # Sort by influence score
        source_analyses.sort(key=lambda x: x["influence_score"], reverse=True)
        
        result = {
            "ok": True,
            "sources": source_analyses,
            "total_sources": len(source_analyses),
            "analysis_period": period,
            "generated_at": datetime.now().isoformat()
        }
        
        # Cache for 2 hours
        set_cached(cache_key, result, 7200)
        return result
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "sources": []
        }

async def get_sentiment_propagation_analysis(period: str = "30d"):
    """
    Revolutionary: Detect how sentiment propagates across news sources
    Information cascade analysis for Philippine media
    """
    cache_key = f"sentiment_propagation:{period}"
    
    # Check cache first - TEMPORARILY DISABLED FOR DEBUGGING
    # cached_result = get_cached(cache_key)
    # if cached_result:
    #     return cached_result
    
    sb = get_supabase()
    
    # Calculate date range
    now = datetime.now()
    if period == "7d":
        start_date = now - timedelta(days=7)
    elif period == "30d":
        start_date = now - timedelta(days=30)
    elif period == "90d":
        start_date = now - timedelta(days=90)
    else:
        start_date = now - timedelta(days=30)
    
    start_date_str = start_date.isoformat()
    
    try:
        # Get multi-source data
        multi_source_data = get_advanced_sentiment_data(sb, start_date_str)
        
        if not multi_source_data:
            return {
                "ok": False,
                "error": "No data available for propagation analysis",
                "propagation": None
            }
        
        # Analyze propagation
        propagation_analysis = analyzer.detect_sentiment_propagation(multi_source_data)
        
        result = {
            "ok": True,
            "propagation": propagation_analysis,
            "data_points": len(multi_source_data),
            "analysis_period": period,
            "generated_at": datetime.now().isoformat()
        }
        
        # Cache for 1 hour
        set_cached(cache_key, result, 3600)
        return result
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "propagation": None
        }

async def get_comprehensive_research_insights(period: str = "30d"):
    """
    Revolutionary: Generate comprehensive research insights for thesis
    First comprehensive sentiment analysis insights for PH media
    """
    cache_key = f"research_insights:{period}"
    
    # Check cache first - TEMPORARILY DISABLED FOR DEBUGGING
    # cached_result = get_cached(cache_key)
    # if cached_result:
    #     return cached_result
    
    sb = get_supabase()
    
    # Calculate date range
    now = datetime.now()
    if period == "7d":
        start_date = now - timedelta(days=7)
    elif period == "30d":
        start_date = now - timedelta(days=30)
    elif period == "90d":
        start_date = now - timedelta(days=90)
    else:
        start_date = now - timedelta(days=30)
    
    start_date_str = start_date.isoformat()
    
    try:
        # Get all data
        all_data = get_advanced_sentiment_data(sb, start_date_str)
        
        if not all_data:
            return {
                "ok": False,
                "error": "No data available for research insights",
                "insights": None
            }
        
        # Generate insights
        total_articles_count = sum(d.get('total', 0) for d in all_data)
        insights = analyzer.generate_research_insights(all_data, total_articles=total_articles_count)
        
        result = {
            "ok": True,
            "insights": insights,
            "data_points": len(all_data),
            "analysis_period": period,
            "generated_at": datetime.now().isoformat()
        }
        
        # Cache for 4 hours
        set_cached(cache_key, result, 14400)
        return result
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "insights": None
        }

async def get_event_sentiment_correlation(period: str = "30d"):
    """
    Revolutionary: Correlate sentiment patterns with real-world events
    First event-sentiment correlation for PH news
    """
    cache_key = f"event_correlation:{period}"
    
    # Check cache first
    cached_result = get_cached(cache_key)
    if cached_result:
        return cached_result
    
    sb = get_supabase()
    
    # Calculate date range
    now = datetime.now()
    if period == "7d":
        start_date = now - timedelta(days=7)
    elif period == "30d":
        start_date = now - timedelta(days=30)
    elif period == "90d":
        start_date = now - timedelta(days=90)
    else:
        start_date = now - timedelta(days=30)
    
    start_date_str = start_date.isoformat()
    
    try:
        # Get sentiment data
        sentiment_data = get_advanced_sentiment_data(sb, start_date_str)
        
        if not sentiment_data:
            return {
                "ok": False,
                "error": "No data available for event correlation",
                "correlations": []
            }
        
        # Mock events data (in real implementation, this would come from external APIs)
        events_data = [
            {"date": "2024-01-15", "type": "political_announcement"},
            {"date": "2024-01-20", "type": "economic_policy"},
            {"date": "2024-01-25", "type": "social_movement"}
        ]
        
        # Analyze correlations
        correlations = analyzer.correlate_with_events(sentiment_data, events_data)
        
        result = {
            "ok": True,
            "correlations": [
                {
                    "event_type": corr.event_type,
                    "correlation_strength": corr.correlation_strength,
                    "lag_days": corr.lag_days,
                    "statistical_significance": corr.statistical_significance,
                    "impact_magnitude": corr.impact_magnitude,
                    "affected_sources": corr.affected_sources
                }
                for corr in correlations
            ],
            "total_correlations": len(correlations),
            "analysis_period": period,
            "generated_at": datetime.now().isoformat()
        }
        
        # Cache for 2 hours
        set_cached(cache_key, result, 7200)
        return result
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "correlations": []
        }


# --- spaCy NLP endpoints ---
async def get_entities(text: str):
    entities = extract_entities(text)
    return {"ok": True, "entities": entities}


async def get_keyphrases(text: str, top_k: int = 10):
    phrases = extract_keyphrases(text, top_k=top_k)
    return {"ok": True, "keyphrases": phrases}

