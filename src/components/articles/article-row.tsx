"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { formatDate } from "@/lib/utils/date";
import { Badge } from "@/components/ui/badge";

interface Article {
  id: string | number;
  title: string;
  url: string | null;
  content: string | null;
  published_at: string | null;
  source: string;
  category: string | null;
}

interface ArticleRowProps {
  sourceValue: string;
  title?: string;
  limit?: number;
}

export default function ArticleRow({ sourceValue, title, limit = 20 }: ArticleRowProps) {
  const [articles, setArticles] = useState<Article[] | null>(null);
  const [error, setError] = useState<unknown | null>(null);
  const [loading, setLoading] = useState(true);
  
  const label = title ?? sourceValue;

  useEffect(() => {
    async function fetchArticles() {
      try {
        setLoading(true);
        const response = await fetch(`/api/articles?source=${encodeURIComponent(sourceValue)}&pageSize=${limit}`);
        const result = await response.json();
        
        if (result.ok) {
          setArticles(result.data);
        } else {
          setError(result.error);
        }
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }

    fetchArticles();
  }, [sourceValue, limit]);

  if (loading) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight">{label}</h2>
          <Badge variant="secondary">Loading...</Badge>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Loading {label} articles...</CardTitle>
            <CardDescription>Please wait while we fetch the latest news.</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold tracking-tight">{label}</h2>
        <Badge variant="secondary">{articles?.length ?? 0}</Badge>
      </div>
      {error ? (
        <Card>
          <CardHeader>
            <CardTitle>Error loading {label}</CardTitle>
            <CardDescription>There was a problem fetching {label} articles.</CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="text-xs whitespace-pre-wrap break-words">{JSON.stringify(error, null, 2)}</pre>
          </CardContent>
        </Card>
      ) : !articles?.length ? (
        <Card>
          <CardHeader>
            <CardTitle>No {label} articles</CardTitle>
            <CardDescription>Try running the scraper for {label}.</CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="overflow-x-auto">
          <div className="flex gap-4 pr-4">
            {articles.map((a) => (
              <Card key={a.id} className="min-w-[280px] max-w-[320px]">
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <CardTitle className="line-clamp-2 text-base">{a.title}</CardTitle>
                      <CardDescription>
                        {a.source} • {a.category || "Uncategorized"}
                      </CardDescription>
                    </div>
                    <Badge variant="outline">{formatDate(a.published_at)}</Badge>
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
        </div>
      )}
    </div>
  );
}
