import { supabaseServer } from "@/lib/supabase/server";

export interface Article {
  id: string | number;
  title: string;
  url: string | null;
  content: string | null;
  published_at: string | null;
  source: string;
  category: string | null;
}

export async function fetchAllArticles(limit: number = 20): Promise<Record<string, Article[]>> {
  const sources = [
    // Removed "ABS-CBN"
    "Manila Times", 
    "GMA",
    "Rappler", 
    "Inquirer",
    "Philstar",
    "Sunstar",
    "Manila Bulletin"
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
  created_at: string;
}

export async function fetchLatestAnalysisByIds(articleIds: (number | string)[]): Promise<Record<string, AnalysisRow | null>> {
  if (!articleIds.length) return {};
  const base = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
  const qs = encodeURIComponent(articleIds.map(String).join(','));
  try {
    const res = await fetch(`${base}/ml/analysis?ids=${qs}`, { cache: 'no-store' });
    const json = await res.json();
    const rows: (AnalysisRow | null)[] = (json?.data || []) as any;
    const map: Record<string, AnalysisRow | null> = {};
    articleIds.forEach((id, idx) => { map[String(id)] = rows[idx] || null; });
    return map;
  } catch {
    const map: Record<string, AnalysisRow | null> = {};
    articleIds.forEach(id => { map[String(id)] = null; });
    return map;
  }
}
