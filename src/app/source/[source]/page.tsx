import Link from "next/link";
import { notFound } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDate } from "@/lib/utils/date";
import { supabaseServer } from "@/lib/supabase/server";
import ArticleCardsInteractive from "@/components/articles/article-cards-interactive";

interface PageProps {
  params: { source: string };
  searchParams: { page?: string; q?: string };
}

const PAGE_SIZE = 20;

export const dynamic = "force-dynamic";

export default async function SourcePage({ params, searchParams }: PageProps) {
  const sourceParam = decodeURIComponent(params.source || "");
  if (!sourceParam) return notFound();

  const page = Math.max(1, Number(searchParams.page || 1));
  const query = (searchParams.q || "").trim();

  const from = (page - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  let queryBuilder = supabaseServer
    .from("articles")
    .select("id,title,url,content,published_at,source,category", { count: "exact" })
    .eq("source", sourceParam)
    .order("published_at", { ascending: false })
    .range(from, to);

  if (query) {
    // Simple full-text like filter on title/content
    queryBuilder = queryBuilder.or(`title.ilike.%${query}%,content.ilike.%${query}%`);
  }

  const { data, error, count } = await queryBuilder;

  if (error) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">{sourceParam}</h1>
        </div>
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
    );
  }

  const total = count ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-center justify-between gap-2">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">{sourceParam}</h1>
          <p className="text-sm text-muted-foreground">{total} articles</p>
        </div>
        <Link href="/" className="text-sm underline">Back to home</Link>
      </div>

      <form className="flex items-center gap-2">
        <input
          type="text"
          name="q"
          defaultValue={query}
          placeholder="Search title or summary..."
          className="w-full md:w-80 border rounded-md px-3 py-2 text-sm"
        />
        <button className="text-sm border rounded-md px-3 py-2">Search</button>
      </form>

      {!data?.length ? (
        <Card>
          <CardHeader>
            <CardTitle>No results</CardTitle>
            <CardDescription>Try a different search or go back.</CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Use interactive cards so users can quick view without leaving the page */}
          <ArticleCardsInteractive articles={data} />
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          {page > 1 && (
            <Link
              href={{ pathname: `/source/${encodeURIComponent(sourceParam)}`, query: { ...(query ? { q: query } : {}), page: page - 1 } }}
              className="text-sm border rounded-md px-3 py-2"
            >
              Previous
            </Link>
          )}
          <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
          {page < totalPages && (
            <Link
              href={{ pathname: `/source/${encodeURIComponent(sourceParam)}`, query: { ...(query ? { q: query } : {}), page: page + 1 } }}
              className="text-sm border rounded-md px-3 py-2"
            >
              Next
            </Link>
          )}
        </div>
      )}
    </div>
  );
} 