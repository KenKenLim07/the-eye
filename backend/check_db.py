from app.core.supabase import get_supabase
sb = get_supabase()
result = sb.table('articles').select('*').order('inserted_at', desc=True).limit(5).execute()
print('Recent articles in database:')
for article in result.data:
    print(f'ID: {article["id"]}, Title: {article["title"][:50]}..., Source: {article["source"]}')
