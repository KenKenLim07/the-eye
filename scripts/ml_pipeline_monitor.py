#!/usr/bin/env python3
"""
Senior Dev ML Pipeline Health Monitor
Monitors ML analysis pipeline health and identifies issues.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.supabase import get_supabase
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_pipeline_health(hours_back: int = 24) -> dict:
    """Check overall ML pipeline health."""
    sb = get_supabase()
    since_time = (datetime.now() - timedelta(hours=hours_back)).isoformat()
    
    health_report = {
        "timestamp": datetime.now().isoformat(),
        "period_hours": hours_back,
        "status": "unknown",
        "metrics": {},
        "issues": [],
        "recommendations": []
    }
    
    try:
        # Get articles scraped in the period
        articles_result = sb.table("articles").select("id,published_at,source").gte("published_at", since_time).execute()
        total_articles = len(articles_result.data or [])
        
        # Get ML analyses created in the period
        analysis_result = sb.table("bias_analysis").select("article_id,created_at").gte("created_at", since_time).execute()
        total_analyses = len(analysis_result.data or [])
        
        # Calculate analysis coverage
        analyzed_article_ids = set(row["article_id"] for row in analysis_result.data or [])
        unanalyzed_articles = [a for a in (articles_result.data or []) if a["id"] not in analyzed_article_ids]
        
        coverage_rate = (total_analyses / total_articles * 100) if total_articles > 0 else 100
        
        health_report["metrics"] = {
            "total_articles_scraped": total_articles,
            "total_ml_analyses": total_analyses,
            "coverage_rate_percent": round(coverage_rate, 2),
            "unanalyzed_count": len(unanalyzed_articles),
            "unanalyzed_articles": [{"id": a["id"], "source": a["source"], "published_at": a["published_at"]} 
                                  for a in unanalyzed_articles[:10]]  # First 10
        }
        
        # Determine status and issues
        if coverage_rate >= 95:
            health_report["status"] = "healthy"
        elif coverage_rate >= 80:
            health_report["status"] = "degraded"
            health_report["issues"].append(f"ML coverage is {coverage_rate:.1f}% (below 95% threshold)")
        else:
            health_report["status"] = "critical"
            health_report["issues"].append(f"ML coverage is critically low: {coverage_rate:.1f}%")
        
        # Add recommendations
        if coverage_rate < 100:
            health_report["recommendations"].append("Run backfill script to process missed articles")
        
        if coverage_rate < 95:
            health_report["recommendations"].append("Check worker logs for ML task failures")
            health_report["recommendations"].append("Verify Celery worker is running and healthy")
        
        # Check for stuck tasks (articles scraped but no analysis after reasonable time)
        stuck_threshold = datetime.now() - timedelta(hours=2)
        stuck_articles = [a for a in unanalyzed_articles 
                         if datetime.fromisoformat(a["published_at"].replace('Z', '+00:00')) < stuck_threshold]
        
        if stuck_articles:
            health_report["issues"].append(f"{len(stuck_articles)} articles stuck without analysis for >2 hours")
            health_report["recommendations"].append("Investigate why these articles weren't analyzed")
        
    except Exception as e:
        health_report["status"] = "error"
        health_report["issues"].append(f"Failed to check pipeline health: {e}")
        logger.error(f"Health check failed: {e}")
    
    return health_report

def print_health_report(report: dict):
    """Print a formatted health report."""
    print("\n" + "="*60)
    print("🔍 ML PIPELINE HEALTH REPORT")
    print("="*60)
    print(f"📅 Time: {report['timestamp']}")
    print(f"⏱️  Period: Last {report['period_hours']} hours")
    
    status_emoji = {
        "healthy": "✅",
        "degraded": "⚠️ ",
        "critical": "🚨",
        "error": "❌",
        "unknown": "❓"
    }
    
    print(f"🏥 Status: {status_emoji.get(report['status'], '❓')} {report['status'].upper()}")
    print()
    
    if report['metrics']:
        metrics = report['metrics']
        print("📊 METRICS:")
        print(f"   📰 Articles scraped: {metrics['total_articles_scraped']}")
        print(f"   🤖 ML analyses: {metrics['total_ml_analyses']}")
        print(f"   📈 Coverage rate: {metrics['coverage_rate_percent']}%")
        print(f"   ❌ Unanalyzed: {metrics['unanalyzed_count']}")
        print()
    
    if report['issues']:
        print("🚨 ISSUES:")
        for issue in report['issues']:
            print(f"   • {issue}")
        print()
    
    if report['recommendations']:
        print("💡 RECOMMENDATIONS:")
        for rec in report['recommendations']:
            print(f"   • {rec}")
        print()
    
    if report['metrics'] and report['metrics']['unanalyzed_articles']:
        print("🔍 SAMPLE UNANALYZED ARTICLES:")
        for article in report['metrics']['unanalyzed_articles'][:5]:
            print(f"   • ID {article['id']} ({article['source']}) - {article['published_at']}")
        if len(report['metrics']['unanalyzed_articles']) > 5:
            print(f"   ... and {len(report['metrics']['unanalyzed_articles']) - 5} more")
        print()

def main():
    """Main monitoring function."""
    import argparse
    parser = argparse.ArgumentParser(description="Monitor ML pipeline health")
    parser.add_argument("--hours", type=int, default=24, help="Hours to look back (default: 24)")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    
    args = parser.parse_args()
    
    report = check_pipeline_health(args.hours)
    
    if args.json:
        import json
        print(json.dumps(report, indent=2))
    else:
        print_health_report(report)

if __name__ == "__main__":
    main()

