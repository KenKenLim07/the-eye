#!/usr/bin/env python3
"""
Senior Dev: Fix funds detection accuracy by reclassifying existing articles
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.supabase import get_supabase
from app.pipeline.store import classify_is_funds
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_funds_accuracy():
    """Reclassify all articles with improved patterns"""
    sb = get_supabase()
    
    try:
        # Get all articles
        logger.info("Fetching all articles...")
        result = sb.table("articles").select("id, title, content, is_funds").execute()
        articles = result.data or []
        
        logger.info(f"Found {len(articles)} articles to reclassify")
        
        updated_count = 0
        funds_count = 0
        non_funds_count = 0
        
        for article in articles:
            article_id = article["id"]
            title = article.get("title", "")
            content = article.get("content", "")
            old_is_funds = article.get("is_funds")
            
            # Reclassify with improved patterns
            new_is_funds = classify_is_funds(title, content)
            
            # Only update if classification changed
            if old_is_funds != new_is_funds:
                try:
                    sb.table("articles").update({"is_funds": new_is_funds}).eq("id", article_id).execute()
                    updated_count += 1
                    logger.info(f"Updated article {article_id}: {old_is_funds} -> {new_is_funds}")
                except Exception as e:
                    logger.error(f"Failed to update article {article_id}: {e}")
            
            if new_is_funds:
                funds_count += 1
            else:
                non_funds_count += 1
        
        logger.info(f"✅ Reclassification complete!")
        logger.info(f"📊 Updated: {updated_count} articles")
        logger.info(f"💰 Funds articles: {funds_count}")
        logger.info(f"🚫 Non-funds articles: {non_funds_count}")
        
        return {
            "updated": updated_count,
            "funds_count": funds_count,
            "non_funds_count": non_funds_count
        }
        
    except Exception as e:
        logger.error(f"Reclassification failed: {e}")
        return None

def check_funds_articles():
    """Check what's currently classified as funds"""
    sb = get_supabase()
    
    try:
        # Get funds articles
        result = sb.table("articles").select("id, title, source, published_at").eq("is_funds", True).order("published_at", desc=True).limit(20).execute()
        funds_articles = result.data or []
        
        logger.info(f"📋 Current funds articles (showing latest 20):")
        for article in funds_articles:
            logger.info(f"  - {article['title'][:80]}... ({article['source']})")
        
        return funds_articles
        
    except Exception as e:
        logger.error(f"Failed to check funds articles: {e}")
        return []

if __name__ == "__main__":
    print("🎯 Senior Dev: Fixing Funds Detection Accuracy")
    print("=" * 50)
    
    # Check current state
    print("\n📋 Current funds articles:")
    current_funds = check_funds_articles()
    
    # Reclassify all articles
    print(f"\n🔧 Reclassifying all articles with improved patterns...")
    result = fix_funds_accuracy()
    
    if result:
        print(f"\n✅ Success! Updated {result['updated']} articles")
        print(f"💰 Funds articles: {result['funds_count']}")
        print(f"🚫 Non-funds articles: {result['non_funds_count']}")
        
        # Check new state
        print(f"\n📋 Updated funds articles:")
        updated_funds = check_funds_articles()
        
        print(f"\n🎯 Next steps:")
        print("1. Check your funds page - it should now be much cleaner")
        print("2. Verify that earthquake/disaster content is filtered out")
        print("3. Confirm that legitimate government funds are still showing")
    else:
        print("❌ Reclassification failed")

