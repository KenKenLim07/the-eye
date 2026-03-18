#!/bin/bash

# Senior Dev Dashboard Integration Script
# Integrates political bias analysis into your existing dashboard

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🎯 Dashboard Integration: Political Bias Analysis${NC}"
echo "=================================================="

# Function to add bias analysis to existing API endpoints
integrate_api() {
    echo -e "${YELLOW}📡 Integrating bias analysis into existing API...${NC}"
    
    # Check if main.py has bias endpoints
    if grep -q "political-bias" backend/app/main.py; then
        echo -e "${GREEN}✅ Political bias endpoints already integrated${NC}"
    else
        echo -e "${YELLOW}⚠️  Political bias endpoints need to be added to main.py${NC}"
    fi
}

# Function to create dashboard data endpoint
create_dashboard_endpoint() {
    echo -e "${YELLOW}📊 Creating comprehensive dashboard data endpoint...${NC}"
    
    cat > backend/app/dashboard_data.py << 'PYTHON_EOF'
"""
Dashboard Data Integration
Senior Dev Approach: Single endpoint for all dashboard data
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from app.core.supabase import get_supabase

router = APIRouter()

@router.get("/dashboard/comprehensive")
async def get_comprehensive_dashboard_data(
    period: str = "7d",
    source: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get comprehensive dashboard data including:
    - Article statistics
    - Sentiment analysis (VADER)
    - Political bias analysis
    - Source comparison
    - Trends over time
    """
    sb = get_supabase()
    
    try:
        # Calculate date range
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
        
        # Get articles
        query = sb.table("articles").select("*").gte("published_at", start_date_str)
        if source:
            query = query.eq("source", source)
        
        articles_result = query.limit(1000).execute()
        articles = articles_result.data or []
        
        if not articles:
            return {
                "ok": True,
                "period": period,
                "source": source,
                "articles": {
                    "total": 0,
                    "by_source": {},
                    "by_date": {}
                },
                "sentiment": {
                    "total_analyses": 0,
                    "avg_compound": 0,
                    "distribution": {"positive": 0, "neutral": 0, "negative": 0}
                },
                "political_bias": {
                    "total_analyses": 0,
                    "avg_bias_score": 0,
                    "avg_confidence": 0,
                    "distribution": {"pro_government": 0, "pro_opposition": 0, "neutral": 0, "mixed": 0}
                },
                "source_comparison": [],
                "timeline": []
            }
        
        article_ids = [a["id"] for a in articles]
        
        # Get sentiment analysis
        sentiment_result = sb.table("bias_analysis").select("*").in_("article_id", article_ids).eq("model_type", "vader").execute()
        sentiment_data = sentiment_result.data or []
        
        # Get political bias analysis
        bias_result = sb.table("bias_analysis").select("*").in_("article_id", article_ids).eq("model_type", "political_bias").execute()
        bias_data = bias_result.data or []
        
        # Process articles by source and date
        articles_by_source = {}
        articles_by_date = {}
        
        for article in articles:
            source_name = article["source"]
            date_str = article["published_at"][:10]
            
            articles_by_source[source_name] = articles_by_source.get(source_name, 0) + 1
            articles_by_date[date_str] = articles_by_date.get(date_str, 0) + 1
        
        # Process sentiment data
        sentiment_stats = {
            "total_analyses": len(sentiment_data),
            "avg_compound": 0,
            "distribution": {"positive": 0, "neutral": 0, "negative": 0}
        }
        
        if sentiment_data:
            total_compound = sum(float(s.get("compound_score", 0)) for s in sentiment_data)
            sentiment_stats["avg_compound"] = round(total_compound / len(sentiment_data), 3)
            
            for s in sentiment_data:
                compound = float(s.get("compound_score", 0))
                if compound > 0.05:
                    sentiment_stats["distribution"]["positive"] += 1
                elif compound < -0.05:
                    sentiment_stats["distribution"]["negative"] += 1
                else:
                    sentiment_stats["distribution"]["neutral"] += 1
        
        # Process political bias data
        bias_stats = {
            "total_analyses": len(bias_data),
            "avg_bias_score": 0,
            "avg_confidence": 0,
            "distribution": {"pro_government": 0, "pro_opposition": 0, "neutral": 0, "mixed": 0}
        }
        
        if bias_data:
            total_bias = sum(float(b.get("political_bias_score", 0)) for b in bias_data)
            total_confidence = sum(float(b.get("confidence_score", 0)) for b in bias_data)
            
            bias_stats["avg_bias_score"] = round(total_bias / len(bias_data), 3)
            bias_stats["avg_confidence"] = round(total_confidence / len(bias_data), 3)
            
            for b in bias_data:
                metadata = b.get("model_metadata", {})
                direction = metadata.get("direction", "neutral")
                if direction in bias_stats["distribution"]:
                    bias_stats["distribution"][direction] += 1
        
        # Create source comparison
        source_comparison = []
        for source_name in articles_by_source.keys():
            source_articles = [a for a in articles if a["source"] == source_name]
            source_article_ids = [a["id"] for a in source_articles]
            
            # Get sentiment for this source
            source_sentiment = [s for s in sentiment_data if s["article_id"] in source_article_ids]
            source_bias = [b for b in bias_data if b["article_id"] in source_article_ids]
            
            source_data = {
                "source": source_name,
                "article_count": len(source_articles),
                "sentiment": {
                    "avg_compound": 0,
                    "distribution": {"positive": 0, "neutral": 0, "negative": 0}
                },
                "political_bias": {
                    "avg_bias_score": 0,
                    "avg_confidence": 0,
                    "distribution": {"pro_government": 0, "pro_opposition": 0, "neutral": 0, "mixed": 0}
                }
            }
            
            if source_sentiment:
                avg_compound = sum(float(s.get("compound_score", 0)) for s in source_sentiment) / len(source_sentiment)
                source_data["sentiment"]["avg_compound"] = round(avg_compound, 3)
                
                for s in source_sentiment:
                    compound = float(s.get("compound_score", 0))
                    if compound > 0.05:
                        source_data["sentiment"]["distribution"]["positive"] += 1
                    elif compound < -0.05:
                        source_data["sentiment"]["distribution"]["negative"] += 1
                    else:
                        source_data["sentiment"]["distribution"]["neutral"] += 1
            
            if source_bias:
                avg_bias = sum(float(b.get("political_bias_score", 0)) for b in source_bias) / len(source_bias)
                avg_conf = sum(float(b.get("confidence_score", 0)) for b in source_bias) / len(source_bias)
                
                source_data["political_bias"]["avg_bias_score"] = round(avg_bias, 3)
                source_data["political_bias"]["avg_confidence"] = round(avg_conf, 3)
                
                for b in source_bias:
                    metadata = b.get("model_metadata", {})
                    direction = metadata.get("direction", "neutral")
                    if direction in source_data["political_bias"]["distribution"]:
                        source_data["political_bias"]["distribution"][direction] += 1
            
            source_comparison.append(source_data)
        
        # Sort by bias score
        source_comparison.sort(key=lambda x: x["political_bias"]["avg_bias_score"], reverse=True)
        
        # Create timeline
        timeline = []
        for date_str in sorted(articles_by_date.keys()):
            date_articles = [a for a in articles if a["published_at"][:10] == date_str]
            date_article_ids = [a["id"] for a in date_articles]
            
            date_sentiment = [s for s in sentiment_data if s["article_id"] in date_article_ids]
            date_bias = [b for b in bias_data if b["article_id"] in date_article_ids]
            
            timeline_entry = {
                "date": date_str,
                "articles": len(date_articles),
                "sentiment": {
                    "avg_compound": 0,
                    "distribution": {"positive": 0, "neutral": 0, "negative": 0}
                },
                "political_bias": {
                    "avg_bias_score": 0,
                    "avg_confidence": 0,
                    "distribution": {"pro_government": 0, "pro_opposition": 0, "neutral": 0, "mixed": 0}
                }
            }
            
            if date_sentiment:
                avg_compound = sum(float(s.get("compound_score", 0)) for s in date_sentiment) / len(date_sentiment)
                timeline_entry["sentiment"]["avg_compound"] = round(avg_compound, 3)
                
                for s in date_sentiment:
                    compound = float(s.get("compound_score", 0))
                    if compound > 0.05:
                        timeline_entry["sentiment"]["distribution"]["positive"] += 1
                    elif compound < -0.05:
                        timeline_entry["sentiment"]["distribution"]["negative"] += 1
                    else:
                        timeline_entry["sentiment"]["distribution"]["neutral"] += 1
            
            if date_bias:
                avg_bias = sum(float(b.get("political_bias_score", 0)) for b in date_bias) / len(date_bias)
                avg_conf = sum(float(b.get("confidence_score", 0)) for b in date_bias) / len(date_bias)
                
                timeline_entry["political_bias"]["avg_bias_score"] = round(avg_bias, 3)
                timeline_entry["political_bias"]["avg_confidence"] = round(avg_conf, 3)
                
                for b in date_bias:
                    metadata = b.get("model_metadata", {})
                    direction = metadata.get("direction", "neutral")
                    if direction in timeline_entry["political_bias"]["distribution"]:
                        timeline_entry["political_bias"]["distribution"][direction] += 1
            
            timeline.append(timeline_entry)
        
        return {
            "ok": True,
            "period": period,
            "source": source,
            "articles": {
                "total": len(articles),
                "by_source": articles_by_source,
                "by_date": articles_by_date
            },
            "sentiment": sentiment_stats,
            "political_bias": bias_stats,
            "source_comparison": source_comparison,
            "timeline": timeline,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "generated_at": datetime.now().isoformat()
        }
PYTHON_EOF
    
    echo -e "${GREEN}✅ Created comprehensive dashboard data endpoint${NC}"
}

# Function to integrate with main.py
integrate_main_py() {
    echo -e "${YELLOW}🔗 Integrating dashboard endpoint with main.py...${NC}"
    
    # Check if dashboard_data is already imported
    if ! grep -q "from app.dashboard_data import" backend/app/main.py; then
        # Add import after other imports
        sed -i '' '/from app.observability.logs import/a\
from app.dashboard_data import router as dashboard_router\
' backend/app/main.py
        
        # Add router
        sed -i '' '/app.include_router(ml_router)/a\
app.include_router(dashboard_router)\
' backend/app/main.py
        
        echo -e "${GREEN}✅ Integrated dashboard endpoint with main.py${NC}"
    else
        echo -e "${GREEN}✅ Dashboard endpoint already integrated${NC}"
    fi
}

# Function to test the integration
test_integration() {
    echo -e "${YELLOW}🧪 Testing dashboard integration...${NC}"
    
    # Test the comprehensive endpoint
    response=$(curl -s "http://localhost:8000/dashboard/comprehensive?period=7d")
    
    if echo "$response" | grep -q '"ok": true'; then
        echo -e "${GREEN}✅ Dashboard integration working${NC}"
        echo "Sample response:"
        echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Articles: {data[\"articles\"][\"total\"]}')
print(f'Sentiment analyses: {data[\"sentiment\"][\"total_analyses\"]}')
print(f'Bias analyses: {data[\"political_bias\"][\"total_analyses\"]}')
print(f'Sources: {len(data[\"source_comparison\"])}')
print(f'Timeline entries: {len(data[\"timeline\"])}')
"
    else
        echo -e "${RED}❌ Dashboard integration failed${NC}"
        echo "$response"
    fi
}

# Main execution
case "${1:-all}" in
    "api")
        integrate_api
        ;;
    "dashboard")
        create_dashboard_endpoint
        integrate_main_py
        ;;
    "test")
        test_integration
        ;;
    "all")
        integrate_api
        create_dashboard_endpoint
        integrate_main_py
        test_integration
        ;;
    *)
        echo "Usage: $0 [api|dashboard|test|all]"
        ;;
esac

echo -e "${GREEN}🎉 Dashboard integration complete!${NC}"
echo "Access your comprehensive dashboard at: http://localhost:8000/dashboard/comprehensive"
