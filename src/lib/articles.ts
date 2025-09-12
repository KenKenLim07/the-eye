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
