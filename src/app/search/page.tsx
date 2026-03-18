import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { supabaseServer } from "@/lib/supabase/server";
import { ArticleCardsInteractive } from "@/components/articles/article-cards-interactive";
import MainLayout from "@/components/layout/main-layout";
import { SearchHeader } from "@/components/search/search-header";

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
      <MainLayout containerSize="xl">
        <div className="space-y-6">
          <SearchHeader
            title="Search"
            subtitle="Find articles across sources"
            backHref="/"
            action="/search"
            queryDefault={q}
            sourceDefault={safeSource}
            sources={[
              { value: "all", label: "All Sources" },
              { value: "GMA", label: "GMA" },
              { value: "Rappler", label: "Rappler" },
              { value: "Inquirer", label: "Inquirer" },
              { value: "Manila Times", label: "Manila Times" },
              { value: "Philstar", label: "Philstar" },
              { value: "Sunstar", label: "Sunstar" },
              { value: "Manila Bulletin", label: "Manila Bulletin" },
            ]}
          />

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
      </MainLayout>
    );
  }

  const total = count ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <MainLayout containerSize="xl">
      <div className="space-y-6">
        <SearchHeader
          title="Search"
          subtitle={`${total} result${total === 1 ? "" : "s"}${safeSource !== "all" ? ` in ${safeSource}` : ""}.`}
          backHref="/"
          action="/search"
          queryDefault={q}
          sourceDefault={safeSource}
          sources={[
            { value: "all", label: "All Sources" },
            { value: "GMA", label: "GMA" },
            { value: "Rappler", label: "Rappler" },
            { value: "Inquirer", label: "Inquirer" },
            { value: "Manila Times", label: "Manila Times" },
            { value: "Philstar", label: "Philstar" },
            { value: "Sunstar", label: "Sunstar" },
            { value: "Manila Bulletin", label: "Manila Bulletin" },
          ]}
        />

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
                href={{
                  pathname: "/search",
                  query: { ...(q ? { q } : {}), ...(safeSource ? { source: safeSource } : {}), page: page + 1 },
                }}
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
