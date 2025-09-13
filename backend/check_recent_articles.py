from app.core.supabase import get_supabase
from datetime import datetime, timedelta
import json

sb = get_supabase()

# Get articles from the last 2 hours
two_hours_ago = (datetime.now() - timedelta(hours=2)).isoformat()
result = sb.table('articles').select('*').gte('inserted_at', two_hours_ago).order('inserted_at', desc=True).execute()

print(f'Articles inserted in last 2 hours: {len(result.data)}')
print('Recent articles:')
for article in result.data:
    print(f'  ID: {article["id"]}, Title: {article["title"][:50]}..., Source: {article["source"]}, Inserted: {article["inserted_at"]}')

# Also check by source
print('\nBy source:')
sources = {}
for article in result.data:
    source = article['source']
    if source not in sources:
        sources[source] = 0
    sources[source] += 1

for source, count in sources.items():
    print(f'  {source}: {count} articles')
