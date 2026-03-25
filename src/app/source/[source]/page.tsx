import Link from "next/link";
import { notFound } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { supabaseServerUntyped } from "@/lib/supabase/server";
import { ArticleCardsInteractive } from "@/components/articles/article-cards-interactive";
import MainLayout from "@/components/layout/main-layout";
import { SearchHeader } from "@/components/search/search-header";
import type { Article } from "@/lib/types";

interface PageProps {
  params: Promise<{ source: string }>;
  searchParams: Promise<{ page?: string; q?: string }>;
}

const PAGE_SIZE = 20;

export const dynamic = "force-dynamic";

function escapeForIlike(input: string): string {
  return input.replace(/([%_\\])/g, "\\$1");
}

export default async function SourcePage({ params, searchParams }: PageProps) {
  const resolvedParams = await params;
  const resolvedSearchParams = await searchParams;
  const sourceParam = decodeURIComponent(resolvedParams.source || "");
  if (!sourceParam) return notFound();

  const page = Math.max(1, Number(resolvedSearchParams.page || 1));
  const query = (resolvedSearchParams.q || "").trim();

  const from = (page - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  const buildBase = () => {
    return supabaseServerUntyped
      .from("articles")
      .select("id,title,url,content,published_at,source,category", { count: "exact" })
      .eq("source", sourceParam)
      .order("published_at", { ascending: false })
      .range(from, to);
  };

  let data: unknown[] | null = null;
  let error: unknown | null = null;
  let count: number | null = null;

  if (query) {
    const fts = await buildBase().textSearch("search_tsv", query, { type: "websearch", config: "simple" });
    if (!fts.error) {
      data = fts.data ?? null;
      count = (fts.count as number | null | undefined) ?? null;
    } else {
      const escaped = escapeForIlike(query);
      const ilike = await buildBase().or(`title.ilike.%${escaped}%,content.ilike.%${escaped}%`);
      data = ilike.data ?? null;
      count = (ilike.count as number | null | undefined) ?? null;
      error = ilike.error ?? fts.error;
    }
  } else {
    const res = await buildBase();
    data = res.data ?? null;
    count = (res.count as number | null | undefined) ?? null;
    error = res.error ?? null;
  }

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

  // Enrich with demo-mode sentiment badges (public table). Non-fatal.
  const rows = ((data as Article[] | null) || []) as Article[];
  let articlesWithSentiment: Article[] = rows;
  if (rows.length > 0) {
    try {
      const ids = rows.map((a) => Number(a.id)).filter(Boolean);
      const sentimentById: Record<number, string | null> = {};
      const batchSize = 250;
      for (let i = 0; i < ids.length; i += batchSize) {
        const batch = ids.slice(i, i + batchSize);
        const { data: srows, error: serr } = await supabaseServerUntyped
          .from("article_sentiment_public")
          .select("article_id,sentiment_label")
          .in("article_id", batch);
        if (serr) throw serr;
        for (const r of srows || []) {
          sentimentById[Number(r.article_id)] = (r.sentiment_label as string | null | undefined) ?? null;
        }
      }
      articlesWithSentiment = rows.map((article) => ({
        ...article,
        sentiment: sentimentById[Number(article.id)] ?? null,
      }));
    } catch {
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
            <ArticleCardsInteractive articles={articlesWithSentiment} layout="grid" />
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
