import { Suspense } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate } from "@/lib/utils/date";

interface Article {
  id: string | number;
  title: string;
  url: string | null;
  content: string | null;
  published_at: string | null;
  source: string;
  category: string | null;
}

interface ArticleRowSuspenseProps {
  sourceValue: string;
  title: string;
  limit?: number;
}

// Loading skeleton component
function ArticleRowSkeleton({ title }: { title: string }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        <Skeleton className="h-6 w-8" />
      </div>
      <div className="overflow-x-auto">
        <div className="flex gap-4 pr-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="min-w-[280px] max-w-[320px]">
              <CardHeader>
                <Skeleton className="h-4 w-3/4 mb-2" />
                <Skeleton className="h-3 w-1/2" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-3 w-full mb-2" />
                <Skeleton className="h-3 w-2/3 mb-2" />
                <Skeleton className="h-3 w-1/2" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

// Server component that fetches data
async function ArticleRowContent({ sourceValue, title, limit = 20 }: ArticleRowSuspenseProps) {
  const { supabaseServer } = await import("@/lib/supabase/server");
  
  const { data: articles, error } = await supabaseServer
    .from("articles")
    .select("*")
    .eq("source", sourceValue)
    .order("published_at", { ascending: false })
    .limit(limit);

  if (error) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
          <Badge variant="destructive">Error</Badge>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Error loading {title}</CardTitle>
            <CardDescription>There was a problem fetching {title} articles.</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  if (!articles?.length) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
          <Badge variant="secondary">0</Badge>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>No {title} articles</CardTitle>
            <CardDescription>Try running the scraper for {title}.</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        <Badge variant="secondary">{articles.length}</Badge>
      </div>
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
    </div>
  );
}

// Main component with Suspense
export default function ArticleRowSuspense(props: ArticleRowSuspenseProps) {
  return (
    <Suspense fallback={<ArticleRowSkeleton title={props.title} />}>
      <ArticleRowContent {...props} />
    </Suspense>
  );
} 