from app.core.supabase import get_supabase
from datetime import datetime, timedelta

sb = get_supabase()

# Check for articles with the specific URLs that caused duplicates
problematic_urls = [
    'https://newsinfo.inquirer.net/category/inquirer-headlines/nation',
    'https://www.gmanetwork.com/news/archives/just_in/',
    'https://www.rappler.com/tachyon/2024/09/Rappler-National-Privacy-Commission-Certificate-2024-2025.png?resize=1772%2C1248&zoom=1'
]

print('Checking for duplicate URLs:')
for url in problematic_urls:
    result = sb.table('articles').select('id, title, source, inserted_at').eq('url', url).execute()
    if result.data:
        article = result.data[0]
        print(f'  URL: {url}')
        print(f'    ID: {article["id"]}, Title: {article["title"]}, Source: {article["source"]}, Inserted: {article["inserted_at"]}')
    else:
        print(f'  URL: {url} - NOT FOUND')

# Check total article count
total_result = sb.table('articles').select('id', count='exact').execute()
print(f'\nTotal articles in database: {total_result.count}')

# Check recent articles (last 24 hours)
yesterday = (datetime.now() - timedelta(days=1)).isoformat()
recent_result = sb.table('articles').select('id', count='exact').gte('inserted_at', yesterday).execute()
print(f'Articles inserted in last 24 hours: {recent_result.count}')
