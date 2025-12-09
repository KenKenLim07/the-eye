#!/usr/bin/env python3
"""Find all forex/stock articles in database"""
import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.supabase import get_supabase

sb = get_supabase()

print('Searching for ALL PhilStar articles with forex/stock patterns...\n')

# Get all PhilStar articles
all_articles = []
offset = 0
while True:
    result = sb.table('articles').select('*').eq('source', 'PhilStar').order('published_at', desc=True).range(offset, offset + 999).execute()
    articles = result.data or []
    if not articles:
        break
    all_articles.extend(articles)
    offset += 1000
    if len(articles) < 1000:
        break

print(f'Found {len(all_articles)} total PhilStar articles\n')

# Search for forex/stock patterns
matches = []
for article in all_articles:
    title = (article.get('title') or '').strip()
    url = (article.get('url') or '').lower()
    content = (article.get('content') or '').lower()
    
    # Check various patterns
    # Numeric pattern like "1$:58.850" or "$58.850"
    if re.match(r'^[\d\$:\.]+$', title) or re.match(r'^\$?\d+[:\.,]\d+$', title):
        matches.append({'id': article.get('id'), 'title': title, 'url': url, 'reason': 'numeric title pattern'})
    elif '/forex-stocks/' in url or '/other-sections/forex-stocks' in url:
        matches.append({'id': article.get('id'), 'title': title, 'url': url, 'reason': 'forex URL'})
    elif 'closing as of' in content[:100]:
        matches.append({'id': article.get('id'), 'title': title, 'url': url, 'reason': 'closing as of content'})
    # Check for "1$:" or "$58" or specific patterns
    elif '1$:' in title or '$58' in title or '1$' in title:
        matches.append({'id': article.get('id'), 'title': title, 'url': url, 'reason': 'title keyword'})

print(f'Found {len(matches)} matching articles:')
print('-' * 100)
for m in matches:
    print(f"ID: {m['id']:>6} | Title: {m['title'][:60]:<60} | {m['reason']}")
    print(f"        URL: {m['url'][:80]}")
print('-' * 100)

# Check specifically for '1$:58.850'
specific = [a for a in all_articles if '1$:58.850' in (a.get('title') or '')]
if specific:
    print(f"\n⚠️  Found article with '1$:58.850':")
    for a in specific:
        print(f"ID: {a.get('id')} | Title: {a.get('title')} | Published: {a.get('published_at')}")
        print(f"URL: {a.get('url')}")
else:
    print("\n✓ No article found with exact title '1$:58.850'")

# Also check for "58.850" anywhere
similar = [a for a in all_articles if '58.850' in (a.get('title') or '') or '58.850' in (a.get('content') or '')]
if similar:
    print(f"\n⚠️  Found {len(similar)} articles with '58.850':")
    for a in similar:
        print(f"ID: {a.get('id')} | Title: {a.get('title')} | URL: {a.get('url')[:60]}")



















