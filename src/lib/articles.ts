import { Article, AnalysisRow } from './types';

export async function fetchArticles(limit: number = 50, offset: number = 0, source?: string): Promise<{ articles: Article[]; total: number }> {
  const params = new URLSearchParams({
    limit: limit.toString(),
    offset: offset.toString(),
  });
  
  if (source) {
    params.append('source', source);
  }

  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_BACKEND_URL}/articles?${params.toString()}`,
      { cache: 'no-store' }
    );
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Failed to fetch articles:', error);
    return { articles: [], total: 0 };
  }
}

export async function fetchLatestAnalysisByIds(articleIds: number[]): Promise<Record<number, AnalysisRow | null>> {
  if (articleIds.length === 0) return {};

  // Limit batch size to prevent timeouts
  const BATCH_SIZE = 50;
  const batches = [];
  for (let i = 0; i < articleIds.length; i += BATCH_SIZE) {
    batches.push(articleIds.slice(i, i + BATCH_SIZE));
  }

  const results: Record<number, AnalysisRow | null> = {};
  
  for (const batch of batches) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout
      
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/ml/analysis?ids=${batch.join(',')}`,
        { 
          cache: 'no-store',
          signal: controller.signal
        }
      );
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        console.log(`HTTP ${response.status} for batch of ${batch.length} articles`);
        continue;
      }
      
      const data = await response.json();
      
      // Check if the response contains an error
      if (data.error) {
        console.log('API returned error for batch:', data.error);
        continue;
      }
      
      // Process the batch results
      const latestByArticle: Record<number, AnalysisRow> = {};
      for (const analysis of data.analysis || []) {
        if (analysis.model_type === "sentiment") {
          const articleId = analysis.article_id;
          if (!latestByArticle[articleId] || new Date(analysis.created_at) > new Date(latestByArticle[articleId].created_at)) {
            latestByArticle[articleId] = analysis;
          }
        }
      }
      // Merge batch results
      Object.assign(results, latestByArticle);
      
    } catch (error: unknown) {
      if (error instanceof Error && error.name === 'AbortError') {
        console.log(`Timeout fetching analysis for batch of ${batch.length} articles`);
      } else {
        console.log(`Error fetching analysis for batch:`, error);
      }
      // Continue with next batch instead of failing completely
    }
  }

  return results;
}

export async function fetchAllArticles(limit: number = 10): Promise<Record<string, Article[]>> {
  try {
    const backendUrl =
      process.env.NEXT_PUBLIC_BACKEND_URL ||
      (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
    if (!backendUrl) {
      console.error("NEXT_PUBLIC_BACKEND_URL is not set; skipping article fetch in production build/runtime.");
      return {};
    }

    // Use optimized single-query endpoint instead of 7 separate queries.
    // In local dev, bypass Redis caching so hotfixes (e.g. published_at corrections) reflect immediately.
    const refreshQS = process.env.NODE_ENV === "development" ? "&refresh=true" : "";
    const response = await fetch(`${backendUrl}/articles/home-optimized?limit_per_source=${limit}${refreshQS}`, {
      cache: 'no-store' 
    });
    
    if (!response.ok) {
      console.error(`Error fetching articles: HTTP ${response.status}`);
      return {};
    }
    
    const data = await response.json();
    const initial = data.articles_by_source || {};
    const canonicalSources = [
      "GMA",
      "Rappler",
      "Inquirer",
      "Manila Times",
      "Philstar",
      "Sunstar",
      "Manila Bulletin",
    ];

    const countFromMap = (map: Record<string, unknown>): number => {
      return Object.values(map).reduce((sum: number, arr: unknown) => {
        return sum + (Array.isArray(arr) ? arr.length : 0);
      }, 0);
    };

    // Self-heal once if all sources are empty due to a transient stale cache snapshot.
    const totalInitial = countFromMap(initial);
    const missingSources = canonicalSources.filter((src) => {
      const rows = initial[src];
      return !Array.isArray(rows) || rows.length === 0;
    });
    const nonEmptySourceCount = canonicalSources.length - missingSources.length;
    const shouldRefresh =
      totalInitial === 0 ||
      (missingSources.length > 0 && nonEmptySourceCount >= canonicalSources.length - 1);

    if (shouldRefresh) {
      const retry = await fetch(`${backendUrl}/articles/home-optimized?limit_per_source=${limit}&refresh=true`, {
        cache: 'no-store'
      });
      if (retry.ok) {
        const retryData = await retry.json();
        const refreshed = retryData.articles_by_source || initial;
        // Prefer refreshed result when it is at least as complete as the initial snapshot.
        return countFromMap(refreshed) >= totalInitial ? refreshed : initial;
      }
    }

    return initial;
  } catch (error) {
    console.error('Error fetching articles:', error);
    return {};
  }
}

export async function fetchTrendsData(period: string = '7d', source?: string): Promise<unknown> {
  try {
    const params = new URLSearchParams({ period });
    if (source) {
      params.append('source', source);
    }
    
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_BACKEND_URL}/ml/trends?${params.toString()}`,
      { cache: 'no-store' }
    );
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch trends data:', error);
    return null;
  }
}

export async function fetchAllArticlesWithSentiment(limit: number = 10): Promise<Record<string, Article[]>> {
  const sources = [
    "GMA",
    "Inquirer", 
    "Philstar",
    "Sunstar",
    "Manila Bulletin",
    "Manila Times",
    "Rappler"
  ];

  // Resolve backend URL with safe default for local dev
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  // Create parallel queries for all sources
  const queries = sources.map(source => 
    fetch(`${backendUrl}/articles?source=${encodeURIComponent(source)}&limit=${limit}&offset=0`, { cache: 'no-store' })
  );

  // Execute all queries in parallel, but don't fail fast if one fetch rejects
  const settled = await Promise.allSettled(queries);
  
  // Process results and collect all article IDs
  const articlesBySource: Record<string, Article[]> = {};
  const allArticleIds: number[] = [];

  for (let i = 0; i < settled.length; i++) {
    const outcome = settled[i];
    const source = sources[i];

    if (outcome.status === 'rejected') {
      console.error(`Error fetching ${source}:`, outcome.reason);
      articlesBySource[source] = [];
      continue;
    }

    const response = outcome.value;

    try {
      if (!response.ok) {
        console.error(`Error fetching ${source}: HTTP ${response.status}`);
        articlesBySource[source] = [];
        continue;
      }
      
      const data = await response.json();
      const articles = data.articles || [];
      articlesBySource[source] = articles;
      
      // Collect article IDs for sentiment analysis
      articles.forEach((article: Article) => {
        if (article.id) {
          allArticleIds.push(Number(article.id));
        }
      });
    } catch (error) {
      console.error(`Error parsing ${source}:`, error);
      articlesBySource[source] = [];
    }
  }

  // Fetch sentiment analysis for all articles
  let sentimentData: Record<number, AnalysisRow | null> = {};
  if (allArticleIds.length > 0) {
    try {
      sentimentData = await fetchLatestAnalysisByIds(allArticleIds);
    } catch (error) {
      console.error('Error fetching sentiment data:', error);
    }
  }

  // Merge sentiment data with articles
  const articlesWithSentiment: Record<string, Article[]> = {};
  
  for (const [source, articles] of Object.entries(articlesBySource)) {
    articlesWithSentiment[source] = articles.map(article => {
      const analysis = sentimentData[Number(article.id)];
      const sentiment = analysis?.sentiment_label || null;
      
      return {
        ...article,
        sentiment: sentiment
      };
    });
  }

  return articlesWithSentiment;
}
