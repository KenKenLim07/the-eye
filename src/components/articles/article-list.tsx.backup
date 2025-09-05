import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { supabaseServer } from "@/lib/supabase/server";

interface Article {
  id: number;
  title: string;
  url: string | null;
  content: string | null;
  published_at: string | null;
  source: string;
  category: string | null;
}

async function loadArticles(): Promise<{ data: Article[] | null; error: unknown | null }> {
  const { data, error } = await supabaseServer
    .from("articles")
    .select("id,title,url,content,published_at,source,category")
    .order("published_at", { ascending: false })
    .limit(12);
  return { data: (data as unknown) as Article[] | null, error };
}

export default async function ArticleList() {
  const { data: articles, error } = await loadArticles();

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Database Error</CardTitle>
          <CardDescription>There was a problem fetching articles.</CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="text-xs whitespace-pre-wrap break-words">{JSON.stringify(error, null, 2)}</pre>
        </CardContent>
      </Card>
    );
  }

  if (!articles?.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>No articles found</CardTitle>
          <CardDescription>Seed mock data to get started.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {articles.map((a) => (
        <Card key={a.id}>
          <CardHeader>
            <div className="flex items-start justify-between gap-2">
              <div>
                <CardTitle className="line-clamp-2">{a.title}</CardTitle>
                <CardDescription>
                  {a.source} • {a.category || "Uncategorized"}
                </CardDescription>
              </div>
              <Badge variant="secondary">{new Date(a.published_at || Date.now()).toLocaleDateString()}</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground line-clamp-3">{a.content || "No summary available."}</p>
            {a.url && (
              <a className="text-sm underline mt-3 inline-block" href={a.url} target="_blank" rel="noreferrer">
                Read more →
              </a>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
} 