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
      for (const analysis of data.analysis || []) {
        if (analysis.model_type === "political_bias") {
          const articleId = analysis.article_id;
          if (!latestByArticle[articleId]) {
            latestByArticle[articleId] = analysis;
          }
        }
      }
      
      // Merge batch results
      Object.assign(results, latestByArticle);
      
    } catch (error) {
      if (error.name === 'AbortError') {
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
  const sources = [
    "GMA",
    "Inquirer", 
    "Philstar",
    "Sunstar",
    "Manila Bulletin",
    "Manila Times",
    "Rappler"
  ];

  // Create parallel queries for all sources
  const queries = sources.map(source => 
    fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/articles?source=${source}&limit=10&offset=0`, { cache: 'no-store' })
  );

  // Execute all queries in parallel
  const results = await Promise.all(queries);
  
  // Process results
  const articlesBySource: Record<string, Article[]> = {};

  for (let i = 0; i < results.length; i++) {
    const response = results[i];
    const source = sources[i];
    
    try {
      if (!response.ok) {
        console.error(`Error fetching ${source}: HTTP ${response.status}`);
        articlesBySource[source] = [];
        continue;
      }
      
      const data = await response.json();
      articlesBySource[source] = data.articles || [];
    } catch (error) {
      console.error(`Error fetching ${source}:`, error);
      articlesBySource[source] = [];
    }
  }

  return articlesBySource;
}

export async function fetchDashboardData(): Promise<any> {
  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_BACKEND_URL}/dashboard/comprehensive`,
      { cache: 'no-store' }
    );
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch dashboard data:', error);
    return null;
  }
}

export async function fetchTrendsData(period: string = '7d', source?: string): Promise<any> {
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

export async function fetchBiasSummary(days: number = 30): Promise<any> {
  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_BACKEND_URL}/bias/summary?days=${days}`,
      { cache: 'no-store' }
    );
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch bias summary:', error);
    return null;
  }
}

export async function fetchBiasArticles(direction?: string, limit: number = 50, offset: number = 0): Promise<any> {
  try {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });
    
    if (direction) {
      params.append('direction', direction);
    }
    
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_BACKEND_URL}/bias/articles?${params.toString()}`,
      { cache: 'no-store' }
    );
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch bias articles:', error);
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

  // Create parallel queries for all sources
  const queries = sources.map(source => 
    fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/articles?source=${source}&limit=${limit}&offset=0`, { cache: 'no-store' })
  );

  // Execute all queries in parallel
  const results = await Promise.all(queries);
  
  // Process results and collect all article IDs
  const articlesBySource: Record<string, Article[]> = {};
  const allArticleIds: number[] = [];

  for (let i = 0; i < results.length; i++) {
    const response = results[i];
    const source = sources[i];
    
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
      console.error(`Error fetching ${source}:`, error);
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
