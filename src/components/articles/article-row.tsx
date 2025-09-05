import { supabaseServer } from "@/lib/supabase/server";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { formatDate } from "@/lib/utils/date";
import { Badge } from "@/components/ui/badge";
import ArticleRowClient from "./article-row-client";

interface Article {
  id: string | number;
  title: string;
  url: string | null;
  content: string | null;
  published_at: string | null;
  source: string;
  category: string | null;
}

async function loadArticlesBySource(sourceValue: string, limit: number = 20) {
  const { data, error } = await supabaseServer
    .from("articles")
    .select("id,title,url,content,published_at,source,category")
    .eq("source", sourceValue)
    .order("published_at", { ascending: false })
    .limit(limit);
  return { data: (data as unknown) as Article[] | null, error };
}

export default async function ArticleRow({ sourceValue, title, limit = 20 }: { sourceValue: string; title?: string; limit?: number; }) {
  const label = title ?? sourceValue;
  
  // Server-side render the initial data
  const { data: initialArticles, error } = await loadArticlesBySource(sourceValue, limit);

  return (
    <ArticleRowClient 
      sourceValue={sourceValue}
      title={title}
      limit={limit}
      initialData={initialArticles}
      initialError={error}
    />
  );
}
