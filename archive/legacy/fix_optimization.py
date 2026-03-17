def get_trends_data_optimized(sb, start_date, source=None):
    """
    FIXED: Database-level aggregation that maintains accuracy and fixes duplicate dates
    """
    try:
        # Use pagination to get ALL articles, not just 1000
        all_articles = []
        offset = 0
        limit_per_batch = 1000
        
        while True:
            query = sb.table('articles').select('published_at, source, id').gte('published_at', start_date)
            
            if source:
                query = query.eq('source', source)
            
            result = query.order('published_at', desc=True).range(offset, offset + limit_per_batch - 1).execute()
            articles = result.data or []
            
            if not articles:
                break
                
            all_articles.extend(articles)
            offset += limit_per_batch
            
            # Safety check
            if len(articles) < limit_per_batch:
                break
        
        if not all_articles:
            return []
        
        # Group by date ONLY (not date + source) to fix duplicate dates
        from collections import defaultdict
        daily_groups = defaultdict(lambda: {'count': 0, 'article_ids': []})
        
        for article in all_articles:
            date_str = article['published_at'][:10]  # YYYY-MM-DD
            
            daily_groups[date_str]['count'] += 1
            daily_groups[date_str]['article_ids'].append(article['id'])
            daily_groups[date_str]['date'] = date_str
        
        # Convert to list format
        daily_summaries = []
        for date_str, data in daily_groups.items():
            daily_summaries.append({
                'date': data['date'],
                'article_count': data['count'],
                'article_ids': data['article_ids']
            })
        
        # Sort by date descending
        daily_summaries.sort(key=lambda x: x['date'], reverse=True)
        return daily_summaries
        
    except Exception as e:
        print(f"Optimized query failed, falling back to original: {e}")
        # Fallback to original method
        articles = get_all_articles_paginated(sb, start_date, source)
        
        # Group by date only
        from collections import defaultdict
        daily_groups = defaultdict(lambda: {'count': 0, 'article_ids': []})
        
        for article in articles:
            date_str = article['published_at'][:10]
            daily_groups[date_str]['count'] += 1
            daily_groups[date_str]['article_ids'].append(article['id'])
            daily_groups[date_str]['date'] = date_str
        
        daily_summaries = []
        for date_str, data in daily_groups.items():
            daily_summaries.append({
                'date': data['date'],
                'article_count': data['count'],
                'article_ids': data['article_ids']
            })
        
        daily_summaries.sort(key=lambda x: x['date'], reverse=True)
        return daily_summaries
