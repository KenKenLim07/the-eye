-- Performance indexes for correlation endpoint
-- Run this in your Supabase SQL editor to speed up correlation queries

-- Composite index for bias_analysis lookups (article_id + model_type)
-- This speeds up queries like: WHERE article_id IN (...) AND model_type = 'sentiment'
CREATE INDEX IF NOT EXISTS idx_bias_analysis_article_model 
ON bias_analysis(article_id, model_type);

-- Index on articles for date range queries with source filtering
-- This speeds up: WHERE published_at >= ? AND published_at <= ? AND source = ?
CREATE INDEX IF NOT EXISTS idx_articles_published_source 
ON articles(published_at DESC, source);

-- Index on sentiment_score for faster aggregations (if needed)
CREATE INDEX IF NOT EXISTS idx_bias_analysis_sentiment_score 
ON bias_analysis(sentiment_score) 
WHERE model_type = 'sentiment' AND sentiment_score IS NOT NULL;

-- Analyze tables to update statistics (helps query planner)
ANALYZE articles;
ANALYZE bias_analysis;




