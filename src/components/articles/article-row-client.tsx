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

interface ArticleRowClientProps {
  sourceValue: string;
  title?: string;
  limit?: number;
  initialData: Article[] | null;
  initialError: unknown | null;
}

export default function ArticleRowClient({ 
  sourceValue, 
  title, 
  limit = 20, 
  initialData, 
  initialError 
}: ArticleRowClientProps) {
  const [articles, setArticles] = useState<Article[] | null>(initialData);
  const [error, setError] = useState<unknown | null>(initialError);
  const [isRefreshing, setIsRefreshing] = useState(false);
  
  const label = title ?? sourceValue;

  // Background refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        setIsRefreshing(true);
        const response = await fetch(`/api/articles?source=${encodeURIComponent(sourceValue)}&pageSize=${limit}`);
        const result = await response.json();
        
        if (result.ok && result.data) {
          setArticles(result.data);
          setError(null);
        } else {
          setError(result.error);
        }
      } catch (err) {
        // Silent fail for background refresh - don't show error to user
        console.warn('Background refresh failed:', err);
      } finally {
        setIsRefreshing(false);
      }
    }, 30000); // Refresh every 30 seconds

    return () => clearInterval(interval);
  }, [sourceValue, limit]);

  // Manual refresh function (can be called by user if needed)
  const handleRefresh = async () => {
    try {
      setIsRefreshing(true);
      const response = await fetch(`/api/articles?source=${encodeURIComponent(sourceValue)}&pageSize=${limit}`);
      const result = await response.json();
      
      if (result.ok && result.data) {
        setArticles(result.data);
        setError(null);
      } else {
        setError(result.error);
      }
    } catch (err) {
      setError(err);
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold tracking-tight">{label}</h2>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{articles?.length ?? 0}</Badge>
          {isRefreshing && (
            <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          )}
        </div>
      </div>
      
      {error ? (
        <Card>
          <CardHeader>
            <CardTitle>Error loading {label}</CardTitle>
            <CardDescription>There was a problem fetching {label} articles.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <pre className="text-xs whitespace-pre-wrap break-words">{JSON.stringify(error, null, 2)}</pre>
              <button 
                onClick={handleRefresh}
                className="text-sm text-blue-600 hover:text-blue-800 underline"
              >
                Try again
              </button>
            </div>
          </CardContent>
        </Card>
      ) : !articles?.length ? (
        <Card>
          <CardHeader>
            <CardTitle>No {label} articles</CardTitle>
            <CardDescription>Try running the scraper for {label}.</CardDescription>
          </CardHeader>
          <CardContent>
            <button 
              onClick={handleRefresh}
              className="text-sm text-blue-600 hover:text-blue-800 underline"
            >
              Refresh
            </button>
          </CardContent>
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
