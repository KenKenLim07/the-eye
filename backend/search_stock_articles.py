#!/usr/bin/env python3
"""Quick script to search for stock market articles by keyword."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.supabase import get_supabase

sb = get_supabase()

# Search for articles with "closing" in title
result = sb.table("articles").select("*").eq("source", "PhilStar").ilike("title", "%closing%").execute()

print(f"Found {len(result.data or [])} PhilStar articles with 'closing' in title:")
print("-" * 100)
for article in result.data or []:
    print(f"ID: {article.get('id')} | Title: {article.get('title')} | URL: {article.get('url', '')[:60]}")
    print(f"Content preview: {(article.get('content') or '')[:200]}...")
    print("-" * 100)

# Search for articles with currency keywords - need to do separate queries
print("\nSearching for currency-related articles...")
all_articles = []
offset = 0
while True:
    result = sb.table("articles").select("*").eq("source", "PhilStar").order("published_at", desc=True).range(offset, offset + 999).execute()
    articles = result.data or []
    if not articles:
        break
    all_articles.extend(articles)
    offset += 1000
    if len(articles) < 1000:
        break

# Filter locally for currency patterns
currency_articles = []
for article in all_articles:
    title = (article.get("title") or "").lower()
    content = (article.get("content") or "").lower()
    if any(word in title or word in content for word in ["$", "peso", "dollar", "closing as of", "1$:"]):
        currency_articles.append(article)

print(f"\nFound {len(currency_articles)} PhilStar articles with currency/closing keywords:")
for article in currency_articles:
    print(f"ID: {article.get('id')} | Title: {article.get('title')} | URL: {article.get('url', '')[:60]}")

