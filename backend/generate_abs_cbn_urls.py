#!/usr/bin/env python3
"""
Generate more ABS-CBN URLs based on working patterns
"""

import random
from datetime import datetime, timedelta

def generate_abs_cbn_urls():
    """Generate potential ABS-CBN URLs based on working patterns"""
    
    base_url = "https://news.abs-cbn.com"
    categories = ['nation', 'business', 'sports', 'entertainment', 'lifestyle', 'technology', 'world']
    
    # Current working URLs for pattern analysis
    working_urls = [
        "https://news.abs-cbn.com/news/nation/2025/9/3/dpwh-ncr-no-ghost-flood-control-projects-in-metro-manila-1735",
        "https://news.abs-cbn.com/news/business/2025/9/3/sec-warns-against-investing-in-pegasus-international-1547",
        "https://news.abs-cbn.com/news/nation/2025/9/3/bfp-delayed-report-blocked-road-hamper-response-to-deadly-malabon-fire-1721",
        "https://news.abs-cbn.com/news/sports/2025/9/3/pba-commissioner-warns-players-about-social-media-posts-1750",
        "https://news.abs-cbn.com/news/business/2025/9/3/airasia-launches-piso-sale-for-reopened-cebu-routes-1751",
    ]
    
    print("🔍 Analyzing working URL patterns...")
    
    # Extract patterns from working URLs
    patterns = []
    for url in working_urls:
        parts = url.split('/')
        if len(parts) >= 8:
            category = parts[4]  # nation, business, etc.
            date_part = '/'.join(parts[5:8])  # 2025/9/3
            article_id = parts[8].split('-')[-1]  # 1735, 1547, etc.
            patterns.append((category, date_part, article_id))
    
    print(f"📊 Found {len(patterns)} working patterns")
    
    # Generate new URLs based on patterns
    new_urls = set()
    
    # Generate for recent dates
    for days_ago in range(0, 5):  # Last 5 days
        date = datetime.now() - timedelta(days=days_ago)
        date_str = date.strftime("%Y/%m/%d")
        
        for category in categories:
            # Generate multiple IDs for each category/date
            for i in range(3):  # 3 URLs per category per day
                # Generate ID similar to working ones (4 digits)
                article_id = random.randint(1000, 9999)
                
                # Create URL with common article title patterns
                title_patterns = [
                    f"breaking-news-{article_id}",
                    f"latest-update-{article_id}",
                    f"news-update-{article_id}",
                    f"report-{article_id}",
                    f"story-{article_id}",
                    f"article-{article_id}",
                    f"news-{article_id}",
                ]
                
                for title_pattern in title_patterns:
                    url = f"{base_url}/news/{category}/{date_str}/{title_pattern}"
                    new_urls.add(url)
    
    # Add some specific patterns based on working URLs
    specific_patterns = [
        "dpwh-official-statement-{id}",
        "government-update-{id}",
        "business-news-{id}",
        "sports-update-{id}",
        "entertainment-news-{id}",
        "lifestyle-tips-{id}",
        "technology-news-{id}",
        "world-news-{id}",
        "breaking-{id}",
        "urgent-{id}",
        "exclusive-{id}",
    ]
    
    for days_ago in range(0, 3):
        date = datetime.now() - timedelta(days=days_ago)
        date_str = date.strftime("%Y/%m/%d")
        
        for category in categories:
            for pattern in specific_patterns:
                article_id = random.randint(1000, 9999)
                title = pattern.format(id=article_id)
                url = f"{base_url}/news/{category}/{date_str}/{title}"
                new_urls.add(url)
    
    return list(new_urls)

if __name__ == "__main__":
    urls = generate_abs_cbn_urls()
    
    print(f"\n🎯 Generated {len(urls)} potential URLs")
    print("\n📋 SAMPLE URLs:")
    for i, url in enumerate(urls[:20]):  # Show first 20
        print(f"  {i+1:2d}. {url}")
    
    print(f"\n💾 ALL {len(urls)} URLs:")
    for url in urls:
        print(f'        "{url}",')
