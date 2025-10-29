#!/usr/bin/env python3
"""
Senior Dev ML Analysis Backfill Script
Identifies and processes articles that were scraped but never analyzed by ML.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.supabase import get_supabase
from app.workers.ml_tasks import analyze_articles_task
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_unanalyzed_articles(since_days: int = 7) -> list[int]:
    """Find articles that were scraped but never analyzed by ML."""
    sb = get_supabase()
    
    # Calculate date threshold
    since_date = (datetime.now() - timedelta(days=since_days)).isoformat()
    
    # Query: Get articles that exist but have no bias analysis
    query = f"""
    SELECT a.id 
    FROM articles a 
    LEFT JOIN bias_analysis ba ON a.id = ba.article_id 
    WHERE a.published_at >= '{since_date}'
    AND ba.article_id IS NULL
    ORDER BY a.published_at DESC
    """
    
    try:
        result = sb.rpc('execute_sql', {'query': query}).execute()
        article_ids = [row['id'] for row in result.data or []]
        logger.info(f"Found {len(article_ids)} unanalyzed articles since {since_date}")
        return article_ids
    except Exception as e:
        logger.error(f"Error finding unanalyzed articles: {e}")
        # Fallback: simpler query
        try:
            # Get recent articles
            articles_result = sb.table("articles").select("id").gte("published_at", since_date).execute()
            all_article_ids = [row["id"] for row in articles_result.data or []]
            
            # Get analyzed articles
            analyzed_result = sb.table("bias_analysis").select("article_id").gte("created_at", since_date).execute()
            analyzed_ids = set(row["article_id"] for row in analyzed_result.data or [])
            
            # Find unanalyzed
            unanalyzed_ids = [aid for aid in all_article_ids if aid not in analyzed_ids]
            logger.info(f"Found {len(unanalyzed_ids)} unanalyzed articles (fallback method)")
            return unanalyzed_ids
        except Exception as e2:
            logger.error(f"Fallback query also failed: {e2}")
            return []

def backfill_analysis(article_ids: list[int], batch_size: int = 50) -> dict:
    """Backfill ML analysis for given article IDs."""
    if not article_ids:
        return {"queued": 0, "errors": []}
    
    logger.info(f"Starting backfill for {len(article_ids)} articles in batches of {batch_size}")
    
    queued = 0
    errors = []
    
    # Process in batches to avoid overwhelming the system
    for i in range(0, len(article_ids), batch_size):
        batch = article_ids[i:i + batch_size]
        try:
            task = analyze_articles_task.delay(batch)
            queued += len(batch)
            logger.info(f"Queued batch {i//batch_size + 1}: {len(batch)} articles (task: {task.id})")
        except Exception as e:
            error_msg = f"Failed to queue batch {i//batch_size + 1}: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    return {
        "queued": queued,
        "errors": errors,
        "total_batches": (len(article_ids) + batch_size - 1) // batch_size
    }

def main():
    """Main backfill function."""
    import argparse
    parser = argparse.ArgumentParser(description="Backfill ML analysis for missed articles")
    parser.add_argument("--days", type=int, default=7, help="Days to look back (default: 7)")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for processing (default: 50)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be processed without queuing")
    
    args = parser.parse_args()
    
    logger.info(f"🔍 Scanning for unanalyzed articles in the last {args.days} days...")
    
    # Find unanalyzed articles
    unanalyzed_ids = find_unanalyzed_articles(args.days)
    
    if not unanalyzed_ids:
        logger.info("✅ No unanalyzed articles found!")
        return
    
    logger.info(f"📊 Found {len(unanalyzed_ids)} unanalyzed articles")
    
    if args.dry_run:
        logger.info("🔍 DRY RUN - Would process these articles:")
        for i, aid in enumerate(unanalyzed_ids[:10]):  # Show first 10
            logger.info(f"  {i+1}. Article ID: {aid}")
        if len(unanalyzed_ids) > 10:
            logger.info(f"  ... and {len(unanalyzed_ids) - 10} more")
        return
    
    # Start backfill
    result = backfill_analysis(unanalyzed_ids, args.batch_size)
    
    logger.info(f"✅ Backfill complete:")
    logger.info(f"   📈 Queued: {result['queued']} articles")
    logger.info(f"   📦 Batches: {result['total_batches']}")
    if result['errors']:
        logger.warning(f"   ⚠️  Errors: {len(result['errors'])}")
        for error in result['errors']:
            logger.warning(f"      - {error}")

if __name__ == "__main__":
    main()

