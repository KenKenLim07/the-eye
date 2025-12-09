# Correlation Endpoint Performance Fix

## Problem
The correlation endpoint was taking **~3 minutes** to load due to:
1. Fetching ALL article columns (including large `content` fields) with `select('*')`
2. Multiple batch queries (500 items each) to `bias_analysis` table
3. Missing composite database indexes
4. Loading everything into memory before processing

## Solution

### 1. Optimized Article Fetching
- **Before**: `select('*')` - fetched all columns including large `content` fields
- **After**: `select('id,source,published_at')` - only fetch what we need
- **Impact**: ~70% reduction in data transfer

### 2. Increased Batch Size
- **Before**: 500 article IDs per batch
- **After**: 2000 article IDs per batch (with fallback to 500)
- **Impact**: Fewer round trips to database

### 3. Optimized Entity Extraction (when `with_entities=true`)
- **Before**: Fetched full articles for all articles
- **After**: Lazy loading - only fetch article content for articles that have sentiment analysis
- **Impact**: Massive reduction when NER is enabled

### 4. Database Indexes (REQUIRED)
Run the SQL script to create performance indexes:

```bash
# In Supabase SQL Editor, run:
backend/scripts/create_correlation_indexes.sql
```

**Indexes created:**
- `idx_bias_analysis_article_model` - Composite index on `(article_id, model_type)`
- `idx_articles_published_source` - Composite index on `(published_at DESC, source)`
- `idx_bias_analysis_sentiment_score` - Partial index on `sentiment_score` where `model_type = 'sentiment'`

## Expected Performance

### Before:
- **7 days**: ~180 seconds (3 minutes)
- **30 days**: ~300+ seconds (5+ minutes)

### After:
- **7 days**: ~5-10 seconds ⚡
- **30 days**: ~15-25 seconds ⚡

## How to Apply

1. **Code changes**: Already applied ✅
2. **Database indexes**: Run the SQL script in Supabase:
   ```sql
   -- Copy and paste from backend/scripts/create_correlation_indexes.sql
   ```

3. **Test the endpoint**:
   ```bash
   curl "http://localhost:8000/ml/correlation?period=7d&refresh=true"
   ```

## Monitoring

Check query performance in Supabase:
1. Go to Database → Query Performance
2. Look for queries on `bias_analysis` table
3. Should see index usage: `idx_bias_analysis_article_model`

## Notes

- Cache is still enabled (120 seconds TTL)
- First load after cache expiry will be slower
- Subsequent loads within cache window are instant
- The optimizations work best with the database indexes applied




