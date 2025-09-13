from app.core.supabase import get_supabase
from datetime import datetime, timedelta
import json

sb = get_supabase()

# Get scraping logs from the last 2 hours
two_hours_ago = (datetime.now() - timedelta(hours=2)).isoformat()
result = sb.table('scraping_logs').select('*').gte('started_at', two_hours_ago).order('started_at', desc=True).execute()

print(f'Scraping runs in last 2 hours: {len(result.data)}')
print('Recent scraping logs:')
for log in result.data:
    print(f'  Source: {log["source"]}, Status: {log["status"]}, Articles: {log["articles_scraped"]}, Started: {log["started_at"]}')
    if log.get('error_message'):
        print(f'    Error: {log["error_message"]}')
