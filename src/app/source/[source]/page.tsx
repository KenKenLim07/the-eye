import Link from "next/link";
import { notFound } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { supabaseServer } from "@/lib/supabase/server";
import { ArticleCardsInteractive } from "@/components/articles/article-cards-interactive";
import MainLayout from "@/components/layout/main-layout";
import { SearchHeader } from "@/components/search/search-header";

interface PageProps {
  params: Promise<{ source: string }>;
  searchParams: Promise<{ page?: string; q?: string }>;
}

const PAGE_SIZE = 20;

export const dynamic = "force-dynamic";

export default async function SourcePage({ params, searchParams }: PageProps) {
  const resolvedParams = await params;
  const resolvedSearchParams = await searchParams;
  const sourceParam = decodeURIComponent(resolvedParams.source || "");
  if (!sourceParam) return notFound();

  const page = Math.max(1, Number(resolvedSearchParams.page || 1));
  const query = (resolvedSearchParams.q || "").trim();

  const from = (page - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  let queryBuilder = supabaseServer
    .from("articles")
    .select("id,title,url,content,published_at,source,category", { count: "exact" })
    .eq("source", sourceParam)
    .order("published_at", { ascending: false })
    .range(from, to);

  if (query) {
    queryBuilder = queryBuilder.or(`title.ilike.%${query}%,content.ilike.%${query}%`);
  }

  const { data, error, count } = await queryBuilder;

  if (error) {
    return (
      <MainLayout containerSize="xl">
        <div className="space-y-6">
          <SearchHeader
            title={sourceParam}
            subtitle="Browse and search within this source"
            backHref="/"
            action={`/source/${encodeURIComponent(sourceParam)}`}
            queryName="q"
            queryDefault={query}
            sources={undefined}
          />
          <Card>
            <CardHeader>
              <CardTitle>Failed to load articles</CardTitle>
              <CardDescription>There was a problem fetching data for {sourceParam}.</CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="text-xs whitespace-pre-wrap break-words">{JSON.stringify(error, null, 2)}</pre>
            </CardContent>
          </Card>
        </div>
      </MainLayout>
    );
  }

  const total = count ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Get sentiment data for articles (optional - don't block if it fails)
  let articlesWithSentiment = data || [];
  
  if (data && data.length > 0) {
    try {
      const articleIds = data.map(a => Number(a.id));
      const response = await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/ml/analysis?ids=${articleIds.join(',')}`, {
        cache: 'no-store'
      });
      
      if (response.ok) {
        const analysisData = await response.json();
        const sentimentAnalysis = analysisData.analysis?.filter((a: { model_type: string }) => a.model_type === 'sentiment') || [];
        
        const sentimentData: Record<number, string> = {};
        sentimentAnalysis.forEach((analysis: { article_id: number; sentiment_label: string }) => {
          sentimentData[analysis.article_id] = analysis.sentiment_label;
        });

        // Merge sentiment data with articles
        articlesWithSentiment = data.map(article => ({
          ...article,
          sentiment: sentimentData[Number(article.id)] || null
        }));
      }
    } catch (error) {
      console.error('Error fetching sentiment data:', error);
      // Continue without sentiment data
    }
  }

  return (
    <MainLayout containerSize="xl">
      <div className="space-y-6">
        <SearchHeader
          title={sourceParam}
          subtitle={`${total} article${total === 1 ? "" : "s"}`}
          backHref="/"
          action={`/source/${encodeURIComponent(sourceParam)}`}
          queryName="q"
          queryDefault={query}
          sources={undefined}
        />

        {!articlesWithSentiment?.length ? (
          <Card>
            <CardHeader>
              <CardTitle>No results</CardTitle>
              <CardDescription>Try a different search.</CardDescription>
            </CardHeader>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <ArticleCardsInteractive articles={articlesWithSentiment} />
          </div>
        )}

        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2">
            {page > 1 && (
              <Link
                href={{ pathname: `/source/${encodeURIComponent(sourceParam)}`, query: { ...(query ? { q: query } : {}), page: page - 1 } }}
                className="text-sm border rounded-md px-3 py-2 bg-card hover:bg-accent/5 transition-colors"
              >
                Previous
              </Link>
            )}
            <span className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Page {page} of {totalPages}
            </span>
            {page < totalPages && (
              <Link
                href={{ pathname: `/source/${encodeURIComponent(sourceParam)}`, query: { ...(query ? { q: query } : {}), page: page + 1 } }}
                className="text-sm border rounded-md px-3 py-2 bg-card hover:bg-accent/5 transition-colors"
              >
                Next
              </Link>
            )}
          </div>
        )}
      </div>
    </MainLayout>
  );
}
