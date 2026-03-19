import MainLayout from "@/components/layout/main-layout";
import ArticleRowServer from "../components/articles/article-row-server";
import { fetchAllArticles, fetchLatestAnalysisByIds } from "@/lib/articles";
import type { AnalysisRow, Article } from "@/lib/types";
import { supabaseServer } from "@/lib/supabase/server";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// In production we often run without a deployed backend; force dynamic so Supabase reads happen at request-time
// instead of being snapshotted during build (which can result in a "blank" homepage until the next revalidate).
export const dynamic = "force-dynamic";

type HomeStats = {
  total_articles: number;
  articles_last_24h: number;
  last_updated: string | null;
  coverage_7d: number | null; // 0..1, null when unavailable
};

type EntityPreview = {
  computed_at: string | null;
  sampled: number | null;
  total_available: number | null;
  items: Array<{
    entity_text: string;
    entity_type: string;
    mentions: number;
    avg_sentiment: number | null;
  }>;
};

async function fetchHomeArticlesFromSupabase(limitPerSource: number): Promise<Record<string, Article[]>> {
  const sources = [
    "GMA",
    "Rappler",
    "Inquirer",
    "Manila Times",
    "Philstar",
    "Sunstar",
    "Manila Bulletin",
  ];

  const results = await Promise.all(
    sources.map(async (src) => {
      const { data, error } = await supabaseServer
        .from("articles")
        .select("id,title,url,content,published_at,source,category")
        .eq("source", src)
        .order("published_at", { ascending: false })
        .limit(limitPerSource);

      if (error) {
        console.error("Home supabase fetch error for source:", src, error);
        return [src, [] as Article[]] as const;
      }
      return [src, ((data as unknown) as Article[] | null) || []] as const;
    })
  );

  return Object.fromEntries(results);
}

async function fetchHomeStatsFromSupabase(): Promise<HomeStats> {
  const now = Date.now();
  const iso24h = new Date(now - 24 * 60 * 60 * 1000).toISOString();
  const iso7d = new Date(now - 7 * 24 * 60 * 60 * 1000).toISOString();

  const [
    totalRes,
    last24hRes,
    lastUpdatedRes,
    articles7dRes,
    sentiment7dRes,
  ] = await Promise.all([
    supabaseServer.from("articles").select("id", { count: "exact", head: true }),
    supabaseServer.from("articles").select("id", { count: "exact", head: true }).gte("published_at", iso24h),
    supabaseServer.from("articles").select("published_at").order("published_at", { ascending: false }).limit(1),
    supabaseServer.from("articles").select("id", { count: "exact", head: true }).gte("published_at", iso7d),
    supabaseServer
      .from("bias_analysis")
      .select("article_id", { count: "exact", head: true })
      .eq("model_type", "sentiment")
      .gte("created_at", iso7d),
  ]);

  const total_articles = totalRes.count ?? 0;
  const articles_last_24h = last24hRes.count ?? 0;
  const last_updated = (lastUpdatedRes.data?.[0]?.published_at as string | null | undefined) ?? null;

  const articles_last_7d = articles7dRes.count ?? null;
  const sentiment_rows_last_7d = sentiment7dRes.count ?? null;
  const coverage_7d =
    typeof articles_last_7d === "number" &&
    articles_last_7d > 0 &&
    typeof sentiment_rows_last_7d === "number"
      ? Math.min(1, Math.max(0, sentiment_rows_last_7d / articles_last_7d))
      : null;

  return { total_articles, articles_last_24h, last_updated, coverage_7d };
}

function snapshotKeyFor(period: "7d" | "30d"): string {
  // Matches src/app/entities/page.tsx and backend/scripts/entity_rankings_snapshot.py
  return `entities:period=${period}:source=all:include_today=1:scan=full:limit=0:cap=0:max=100`;
}

function snapshotKeyFallbacks(period: "7d" | "30d"): string[] {
  return [
    snapshotKeyFor(period),
    `entities:period=${period}:source=all:include_today=1:scan=fast:limit=500:cap=1000:max=100`,
  ];
}

async function fetchEntityPreviewFromSnapshots(period: "7d" | "30d" = "7d"): Promise<EntityPreview> {
  const keys = snapshotKeyFallbacks(period);

  const snapRes = await supabaseServer
    .from("entity_rankings_snapshots")
    .select("key,computed_at,sampled,total_available")
    .in("key", keys)
    .order("computed_at", { ascending: false })
    .limit(1);

  const snap = snapRes.data?.[0];
  if (!snap?.key) {
    return { computed_at: null, sampled: null, total_available: null, items: [] };
  }

  const itemsRes = await supabaseServer
    .from("entity_rankings_items")
    .select("entity_text,entity_type,mentions,avg_sentiment")
    .eq("snapshot_key", snap.key)
    .order("mentions", { ascending: false })
    .limit(10);

  return {
    computed_at: (snap.computed_at as string | null | undefined) ?? null,
    sampled: (snap.sampled as number | null | undefined) ?? null,
    total_available: (snap.total_available as number | null | undefined) ?? null,
    items: (itemsRes.data ?? []) as EntityPreview["items"],
  };
}

export default async function Home() {
  const t0 = Date.now();
  const [stats, entityPreview] = await Promise.all([
    fetchHomeStatsFromSupabase().catch((e) => {
      console.error("Home stats fetch failed:", e);
      return { total_articles: 0, articles_last_24h: 0, last_updated: null, coverage_7d: null } as HomeStats;
    }),
    fetchEntityPreviewFromSnapshots("7d").catch((e) => {
      console.error("Home entity preview fetch failed:", e);
      return { computed_at: null, sampled: null, total_available: null, items: [] } as EntityPreview;
    }),
  ]);

  // Fetch latest articles per source using optimized single endpoint
  const PER_SOURCE_LIMIT = 10;
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "";
  const hasBackend =
    !!backendUrl &&
    (process.env.NODE_ENV === "development" ||
      (!backendUrl.includes("localhost") && !backendUrl.includes("127.0.0.1")));
  const articlesBySource = hasBackend
    ? await fetchAllArticles(PER_SOURCE_LIMIT)
    : await fetchHomeArticlesFromSupabase(PER_SOURCE_LIMIT);
  const tAfterOptimized = Date.now();

  // Normalize backend source keys to canonical labels used in UI
  const canonicalOrder = [
    "GMA",
    "Rappler",
    "Inquirer",
    "Manila Times",
    "Philstar",
    "Sunstar",
    "Manila Bulletin",
  ];

  // Normalize function: lowercase and remove non-alphanumerics for resilient matching
  const normalizeName = (s: string) => (s || "").toLowerCase().replace(/[^a-z0-9]/g, "");

  const variants: Record<string, string[]> = {
    GMA: ["gma", "gmanews", "gmanetwork"],
    Rappler: ["rappler"],
    Inquirer: ["inquirer", "philippinedailyinquirer", "inquirernet", "inquirer\u002Enet"],
    "Manila Times": ["manilatimes", "themanilatimes"],
    Philstar: ["philstar", "philstarcom", "philstar\u002Ecom", "philstarcomph"],
    Sunstar: ["sunstar", "sunstarph"],
    "Manila Bulletin": ["manilabulletin", "mb", "manila\u002Ebulletin"],
  };

  // Log raw incoming keys and counts to aid diagnosis
  try {
    const debugCounts = Object.fromEntries(
      Object.entries(articlesBySource).map(([k, v]) => [k, Array.isArray(v) ? v.length : 0])
    );
    console.log("Home debug: raw source counts", debugCounts);
  } catch {}

  // Regroup by each article's own source field using robust normalization
  const normalizedBySource = Object.fromEntries(
    canonicalOrder.map((k) => [k, [] as Article[]])
  ) as Record<string, Article[]>;

  const allArticlesFlat: Article[] = Object.values(articlesBySource).flat();
  for (const article of allArticlesFlat) {
    const src = normalizeName(String(article?.source || ""));
    let placed = false;
    for (const [canonical, names] of Object.entries(variants)) {
      if (names.some((n) => src === n)) {
        normalizedBySource[canonical].push(article);
        placed = true;
        break;
      }
    }
    if (!placed) {
      // Unmapped sources are ignored from the home rows
    }
  }

  // No frontend top-up: rely on backend to deliver up to PER_SOURCE_LIMIT per source

  // Log final post-top-up counts
  try {
    const finalCounts = Object.fromEntries(
      Object.entries(normalizedBySource).map(([k, v]) => [k, Array.isArray(v) ? v.length : 0])
    );
    console.log("Home debug: final source counts", finalCounts);
  } catch {}

  // Collect all article IDs for a single batched sentiment fetch
  const allArticleIds: number[] = Object.values(normalizedBySource)
    .flat()
    .map((a) => Number(a.id))
    .filter(Boolean);

  // Fetch latest sentiment/bias analysis in one request (optional; non-fatal if fails)
  let analysisById: Record<number, AnalysisRow | null> = {};
  if (hasBackend && allArticleIds.length > 0) {
    try {
      analysisById = await fetchLatestAnalysisByIds(allArticleIds);
    } catch (err) {
      console.error("Failed to fetch analysis for home articles:", err);
    }
  }
  const tAfterAnalysis = Date.now();

  // Merge sentiment into articles before rendering
  const enrichedBySource: Record<string, Article[]> = {};
  for (const [source, articles] of Object.entries(normalizedBySource)) {
    enrichedBySource[source] = (articles || []).map((article) => {
      const analysis = analysisById[Number(article.id)];
      const sentiment = analysis?.sentiment_label || null;
      return { ...article, sentiment };
    });
  }
  const t1 = Date.now();
  console.log("Home debug: timings ms", {
    optimizedFetch: tAfterOptimized - t0,
    topUpAndGroup: tAfterAnalysis - tAfterOptimized,
    enrichAndRenderPrep: t1 - tAfterAnalysis,
    total: t1 - t0,
  });

  return (
    <MainLayout>
      <div className="space-y-8 mt-10">
        <div className="text-center space-y-2">
          <h1 className="u-serif text-4xl font-semibold tracking-tight">Philippine News</h1>
          <p className="text-sm text-muted-foreground">
            Latest headlines aggregated from top PH news sources
          </p>
        </div>

        <div className="max-w-3xl mx-auto">
          <form className="flex flex-col md:flex-row items-stretch gap-2" action="/search" method="get">
            <select
              name="source"
              defaultValue="all"
              className="border rounded-md px-3 py-2 text-sm md:w-56 bg-card"
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
              placeholder="Search headlines or summaries..."
              className="flex-1 border rounded-md px-3 py-2 text-sm bg-card"
            />
            <button className="text-sm border rounded-md px-4 py-2 bg-card hover:bg-accent/5 transition-colors">Search</button>
          </form>
          <div className="text-xs text-muted-foreground mt-2 text-center">
            Tip: use <Link className="underline" href="/search">Advanced search</Link> for pagination.
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-end justify-between gap-3">
            <div>
              <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">At a glance</div>
              <div className="u-serif text-2xl font-semibold tracking-tight">Today’s pulse</div>
            </div>
            <div className="hidden sm:block text-xs text-muted-foreground">
              {stats.last_updated ? `Updated ${new Date(stats.last_updated).toLocaleString()}` : ""}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Total Articles</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="u-serif text-3xl font-semibold tabular-nums">{stats.total_articles.toLocaleString()}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Last 24 Hours</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="u-serif text-3xl font-semibold tabular-nums">{stats.articles_last_24h.toLocaleString()}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Sources</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="u-serif text-3xl font-semibold tabular-nums">7</div>
                <div className="text-xs text-muted-foreground mt-1">GMA, Rappler, Inquirer, Manila Times, Philstar, Sunstar, Manila Bulletin</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Sentiment Coverage (7d)</CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="u-serif text-3xl font-semibold tabular-nums">
                  {typeof stats.coverage_7d === "number" ? `${Math.round(stats.coverage_7d * 100)}%` : "—"}
                </div>
                <div className="text-xs text-muted-foreground mt-1">Articles with VADER sentiment rows</div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div>
                <CardTitle>Top Entities (7d)</CardTitle>
                <div className="text-sm text-muted-foreground">
                  {entityPreview.computed_at ? `Updated ${new Date(entityPreview.computed_at).toLocaleString()}. ` : ""}
                  {typeof entityPreview.sampled === "number" ? `Sampled: ${entityPreview.sampled}` : ""}
                  {typeof entityPreview.total_available === "number" ? ` (available: ${entityPreview.total_available})` : ""}
                </div>
              </div>
              <Link className="text-sm underline text-accent hover:text-accent/80" href="/entities">
                View full ranking
              </Link>
            </CardHeader>
            <CardContent>
              {entityPreview.items.length === 0 ? (
                <div className="text-sm text-muted-foreground py-2">No snapshot data yet. Run the snapshot generator to populate rankings.</div>
              ) : (
                <div className="overflow-auto">
                  <table className="min-w-full text-sm">
                    <thead className="border-b">
                      <tr>
                        <th className="text-left p-2 u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Rank</th>
                        <th className="text-left p-2 u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Entity</th>
                        <th className="text-right p-2 u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Mentions</th>
                        <th className="text-right p-2 u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Avg</th>
                      </tr>
                    </thead>
                    <tbody>
                      {entityPreview.items.map((it, idx) => (
                        <tr key={`${it.entity_text}:${it.entity_type}:${idx}`} className="border-t">
                          <td className="p-2 u-mono text-[11px] text-muted-foreground">{idx + 1}</td>
                          <td className="p-2">
                            <div className="font-medium">{it.entity_text}</div>
                            <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">{it.entity_type}</div>
                          </td>
                          <td className="p-2 text-right u-mono text-[11px] tabular-nums">{it.mentions}</td>
                          <td className="p-2 text-right u-mono text-[11px] tabular-nums text-muted-foreground">
                            {typeof it.avg_sentiment === "number" ? it.avg_sentiment.toFixed(3) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-8">
          <ArticleRowServer 
            articles={enrichedBySource["GMA"] || []} 
            title="GMA News" 
            sourceValue="GMA" 
          />
          <ArticleRowServer 
            articles={enrichedBySource["Rappler"] || []} 
            title="Rappler" 
            sourceValue="Rappler" 
          />
          <ArticleRowServer 
            articles={enrichedBySource["Inquirer"] || []} 
            title="Inquirer" 
            sourceValue="Inquirer" 
          />
          <ArticleRowServer 
            articles={enrichedBySource["Manila Times"] || []} 
            title="Manila Times" 
            sourceValue="Manila Times"
          />
          <ArticleRowServer 
            articles={enrichedBySource["Philstar"] || []} 
            title="Philstar" 
            sourceValue="Philstar" 
          />
          <ArticleRowServer 
            articles={enrichedBySource["Sunstar"] || []} 
            title="Sunstar" 
            sourceValue="Sunstar" 
          />
          <ArticleRowServer 
            articles={enrichedBySource["Manila Bulletin"] || []} 
            title="Manila Bulletin" 
            sourceValue="Manila Bulletin" 
          />
        </div>
      </div>
    </MainLayout>
  );
}
