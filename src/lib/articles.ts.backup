import { createClient } from "@supabase/supabase-js";

const supabaseServer = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export interface Article {
  id: number;
  source: string;
  category: string | null;
  raw_category: string | null;
  title: string;
  url: string;
  content: string;
  published_at: string;
  created_at: string;
}

export async function fetchAllArticles(limit: number = 10): Promise<Record<string, Article[]>> {
  const sources = [
    "GMA",
    "Inquirer",
    "Philstar",  // Fixed: was "PhilStar"
    "Sunstar",
    "Manila Bulletin",
    "Manila Times",
    "Rappler"
  ];

  // Create parallel queries for all sources
  const queries = sources.map(source => 
    supabaseServer
      .from("articles")
      .select("*")
      .eq("source", source)
      .order("published_at", { ascending: false })
      .limit(limit)
  );

  // Execute all queries in parallel
  const results = await Promise.all(queries);
  
  // Process results
  const articlesBySource: Record<string, Article[]> = {};

  results.forEach((result, index) => {
    const source = sources[index];
    if (result.error) {
      console.error(`Error fetching ${source}:`, result.error);
      articlesBySource[source] = [];
    } else {
      articlesBySource[source] = (result.data as Article[]) || [];
    }
  });

  return articlesBySource;
}

export interface AnalysisRow {
  id: number;
  article_id: number;
  model_version: string;
  model_type: string;
  sentiment_score: number | null;
  sentiment_label: string | null;
  confidence_score: number | null;
  processing_time_ms: number | null;
  model_metadata: any;
  created_at: string;
}

export interface BulkAnalysisResponse {
  analysis: AnalysisRow[];
}

export async function fetchLatestAnalysisByIds(articleIds: number[]): Promise<Record<number, AnalysisRow | null>> {
  if (articleIds.length === 0) return {};

  try {
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_BACKEND_URL}/ml/analysis?ids=${articleIds.join(',')}`,
      { cache: 'no-store' }
    );
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const data = await response.json();
    
    // Check if the response contains an error
    if (data.error) {
      console.error('API returned error:', data.error);
      return {};
    }
    
    // Check if data.analysis exists and is an array
    if (!data.analysis || !Array.isArray(data.analysis)) {
      console.error('Invalid response format:', data);
      return {};
    }
    
    const analysisMap: Record<number, AnalysisRow | null> = {};
    
    // Group by article_id and prioritize sentiment analysis over political bias
    const latestByArticle: Record<number, AnalysisRow> = {};
    
    // First pass: collect all sentiment analyses
    for (const analysis of data.analysis) {
      if (analysis.model_type === "sentiment") {
        const articleId = analysis.article_id;
        if (!latestByArticle[articleId] || new Date(analysis.created_at) > new Date(latestByArticle[articleId].created_at)) {
          latestByArticle[articleId] = analysis;
        }
      }
    }
    
    // Second pass: fill in missing articles with political bias analysis
    for (const analysis of data.analysis) {
      if (analysis.model_type === "political_bias") {
        const articleId = analysis.article_id;
        if (!latestByArticle[articleId]) {
          latestByArticle[articleId] = analysis;
        }
      }
    }
    
    // Create the final map
    for (const articleId of articleIds) {
      analysisMap[articleId] = latestByArticle[articleId] || null;
    }
    
    return analysisMap;
  } catch (error) {
    console.error('Failed to fetch analysis:', error);
    return {};
  }
}
