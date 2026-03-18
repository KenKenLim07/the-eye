import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { supabaseServer } from "@/lib/supabase/server";
import { ArticleCardsInteractive } from "@/components/articles/article-cards-interactive";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 24;
const SOURCES = [
  "all",
  "GMA",
  "Rappler",
  "Inquirer",
  "Manila Times",
  "Philstar",
  "Sunstar",
  "Manila Bulletin",
];

type SearchParams = Promise<{ q?: string; source?: string; page?: string }>;

export default async function SearchPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const q = (sp.q || "").trim();
  const source = (sp.source || "all").trim() || "all";
  const page = Math.max(1, Number(sp.page || 1));

  const from = (page - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  const safeSource = SOURCES.includes(source) ? source : "all";

  let queryBuilder = supabaseServer
    .from("articles")
    .select("id,title,url,content,published_at,source,category", { count: "exact" })
    .order("published_at", { ascending: false })
    .range(from, to);

  if (safeSource !== "all") {
    queryBuilder = queryBuilder.eq("source", safeSource);
  }

  if (q) {
    // Search in title or content. Keep it simple and fast for demo.
    queryBuilder = queryBuilder.or(`title.ilike.%${q}%,content.ilike.%${q}%`);
  }

  const { data, error, count } = await queryBuilder;

  if (error) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
        <div className="flex items-center justify-between gap-2">
          <div className="space-y-1">
            <h1 className="text-2xl font-semibold">Search</h1>
            <p className="text-sm text-muted-foreground">Find articles across sources</p>
          </div>
          <Link href="/" className="text-sm underline">
            Back to home
          </Link>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Failed to load results</CardTitle>
            <CardDescription>There was a problem fetching search results.</CardDescription>
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
          <h1 className="text-2xl font-semibold">Search</h1>
          <p className="text-sm text-muted-foreground">
            {total} result{total === 1 ? "" : "s"}
            {safeSource !== "all" ? ` in ${safeSource}` : ""}.
          </p>
        </div>
        <Link href="/" className="text-sm underline">
          Back to home
        </Link>
      </div>

      <form className="flex flex-col md:flex-row items-stretch gap-2" action="/search" method="get">
        <select
          name="source"
          defaultValue={safeSource}
          className="border rounded-md px-3 py-2 text-sm md:w-56 bg-background"
        >
          <option value="all">All Sources</option>
          <option value="GMA">GMA</option>
          <option value="Rappler">Rappler</option>
          <option value="Inquirer">Inquirer</option>
          <option value="Manila Times">Manila Times</option>
          <option value="Philstar">Philstar</option>
          <option value="Sunstar">Sunstar</option>
          <option value="Manila Bulletin">Manila Bulletin</option>
        </select>
        <input
          type="text"
          name="q"
          defaultValue={q}
          placeholder="Search title or summary..."
          className="flex-1 border rounded-md px-3 py-2 text-sm"
        />
        <button className="text-sm border rounded-md px-4 py-2">Search</button>
      </form>

      {!data?.length ? (
        <Card>
          <CardHeader>
            <CardTitle>No results</CardTitle>
            <CardDescription>Try a different query or source filter.</CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <ArticleCardsInteractive articles={data} />
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          {page > 1 && (
            <Link
              href={{
                pathname: "/search",
                query: { ...(q ? { q } : {}), ...(safeSource ? { source: safeSource } : {}), page: page - 1 },
              }}
              className="text-sm border rounded-md px-3 py-2"
            >
              Previous
            </Link>
          )}
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          {page < totalPages && (
            <Link
              href={{
                pathname: "/search",
                query: { ...(q ? { q } : {}), ...(safeSource ? { source: safeSource } : {}), page: page + 1 },
              }}
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

