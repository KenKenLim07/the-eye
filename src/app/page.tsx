import MainLayout from "@/components/layout/main-layout";
import ArticleRowServer from "../components/articles/article-row-server";
import { fetchAllArticles, fetchLatestAnalysisByIds } from "@/lib/articles";
import type { AnalysisRow, Article } from "@/lib/types";
import { supabaseServer, supabaseServerUntyped } from "@/lib/supabase/server";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import HomeControlBar from "@/components/home/control-bar";
import LatestFeed from "@/components/home/latest-feed";
import SentimentSplitCard from "@/components/home/sentiment-split-card";

// In production we often run without a deployed backend; force dynamic so Supabase reads happen at request-time
// instead of being snapshotted during build (which can result in a "blank" homepage until the next revalidate).
export const dynamic = "force-dynamic";

type HomeStats = {
  total_articles: number;
  articles_last_24h: number;
  last_updated: string | null;
  coverage_7d: number | null; // 0..1, null when unavailable
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
    sentimentCoverage7dRes,
  ] = await Promise.all([
    supabaseServer.from("articles").select("id", { count: "exact", head: true }),
    supabaseServer.from("articles").select("id", { count: "exact", head: true }).gte("published_at", iso24h),
    supabaseServer.from("articles").select("published_at").order("published_at", { ascending: false }).limit(1),
    supabaseServer.from("articles").select("id", { count: "exact", head: true }).gte("published_at", iso7d),
    // `bias_analysis` is not publicly readable under typical Supabase RLS, so compute
    // coverage using the public per-article sentiment cache table.
    supabaseServerUntyped
      .from("articles")
      .select("id, article_sentiment_public!inner(article_id)", { count: "exact", head: true })
      .gte("published_at", iso7d),
  ]);

  const total_articles = totalRes.count ?? 0;
  const articles_last_24h = last24hRes.count ?? 0;
  const last_updated = (lastUpdatedRes.data?.[0]?.published_at as string | null | undefined) ?? null;

  const articles_last_7d = articles7dRes.count ?? null;
  let sentiment_rows_last_7d = sentimentCoverage7dRes.count ?? null;

  // Fallback when PostgREST embedded joins aren't available (missing FK relationship).
  // Compute coverage by fetching article IDs then counting sentiment rows for those IDs.
  if (
    typeof articles_last_7d === "number" &&
    articles_last_7d > 0 &&
    (sentiment_rows_last_7d === null || sentimentCoverage7dRes.error)
  ) {
    try {
      if (sentimentCoverage7dRes.error) {
        console.warn("Coverage join query failed; falling back to batched IN queries:", sentimentCoverage7dRes.error);
      }

      const pageSize = 1000;
      let offset = 0;
      const articleIds: number[] = [];

      while (true) {
        const { data, error } = await supabaseServer
          .from("articles")
          .select("id")
          .gte("published_at", iso7d)
          .order("published_at", { ascending: false })
          .range(offset, offset + pageSize - 1);

        if (error) {
          console.warn("Coverage fallback: failed to fetch article ids:", error);
          break;
        }

        const rows = (data as Array<{ id: number }> | null) || [];
        for (const r of rows) articleIds.push(Number(r.id));

        if (rows.length < pageSize) break;
        offset += pageSize;
        // Hard safety cap to keep the homepage fast in degenerate cases.
        if (articleIds.length > 8000) break;
      }

      const chunkSize = 500;
      let analyzed = 0;
      for (let i = 0; i < articleIds.length; i += chunkSize) {
        const chunk = articleIds.slice(i, i + chunkSize);
        const { count, error } = await supabaseServerUntyped
          .from("article_sentiment_public")
          .select("article_id", { count: "exact", head: true })
          .in("article_id", chunk);

        if (error) {
          console.warn("Coverage fallback: failed to count sentiment rows:", error);
          analyzed = 0;
          break;
        }
        analyzed += count ?? 0;
      }

      sentiment_rows_last_7d = analyzed;
    } catch (e) {
      console.warn("Coverage fallback failed:", e);
    }
  }
  const coverage_7d =
    typeof articles_last_7d === "number" &&
    articles_last_7d > 0 &&
    typeof sentiment_rows_last_7d === "number"
      ? Math.min(1, Math.max(0, sentiment_rows_last_7d / articles_last_7d))
      : null;

  return { total_articles, articles_last_24h, last_updated, coverage_7d };
}

export default async function Home() {
  const t0 = Date.now();
  const stats = await fetchHomeStatsFromSupabase().catch((e) => {
    console.error("Home stats fetch failed:", e);
    return { total_articles: 0, articles_last_24h: 0, last_updated: null, coverage_7d: null } as HomeStats;
  });

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

  // Fetch latest sentiment labels (optional; non-fatal if fails).
  // - If backend exists: use backend bulk endpoint (fast, richer)
  // - If no backend: use Supabase public cache table (demo mode)
  let analysisById: Record<number, AnalysisRow | null> = {};
  const sentimentById: Record<number, string | null> = {};

  if (allArticleIds.length > 0) {
    if (hasBackend) {
      try {
        analysisById = await fetchLatestAnalysisByIds(allArticleIds);
      } catch (err) {
        console.error("Failed to fetch analysis for home articles:", err);
      }
    } else {
      try {
        const batchSize = 250;
        for (let i = 0; i < allArticleIds.length; i += batchSize) {
          const batch = allArticleIds.slice(i, i + batchSize);
          const { data, error } = await supabaseServerUntyped
            .from("article_sentiment_public")
            .select("article_id,sentiment_label")
            .in("article_id", batch);
          if (error) throw error;
          for (const r of data || []) {
            const id = Number(r.article_id);
            sentimentById[id] = (r.sentiment_label as string | null | undefined) ?? null;
          }
        }
      } catch (err) {
        console.error("Failed to fetch demo sentiment badges:", err);
      }
    }
  }
  const tAfterAnalysis = Date.now();

  // Merge sentiment into articles before rendering
  const enrichedBySource: Record<string, Article[]> = {};
  for (const [source, articles] of Object.entries(normalizedBySource)) {
    enrichedBySource[source] = (articles || []).map((article) => {
      const id = Number(article.id);
      const analysis = analysisById[id];
      const sentiment = hasBackend ? (analysis?.sentiment_label || null) : (sentimentById[id] ?? null);
      return { ...article, sentiment };
    });
  }

  const visibleArticles: Article[] = Object.values(enrichedBySource).flat();
  const sentimentSplit = visibleArticles.reduce(
    (acc, a) => {
      const s = (a.sentiment || "").toLowerCase();
      if (s === "positive") acc.positive += 1;
      else if (s === "negative") acc.negative += 1;
      else if (s === "neutral") acc.neutral += 1;
      else acc.unlabeled += 1;
      return acc;
    },
    { positive: 0, neutral: 0, negative: 0, unlabeled: 0 }
  );

  const coveragePct = typeof stats.coverage_7d === "number" ? Math.round(stats.coverage_7d * 100) : null;
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

        <div className="max-w-4xl mx-auto">
          <HomeControlBar sources={canonicalOrder} lastUpdated={stats.last_updated} />
          <div className="text-xs text-muted-foreground mt-2 text-center">
            Tip: use <Link className="underline" href="/search">Advanced search</Link> for pagination.
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-end justify-between gap-3">
            <div className="space-y-1">
              <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">At a glance</div>
              <div className="u-serif text-xl sm:text-2xl font-semibold tracking-tight">Today’s pulse</div>
              <div className="sm:hidden text-xs text-muted-foreground">
                {stats.last_updated ? `Updated ${new Date(stats.last_updated).toLocaleString()}` : ""}
              </div>
            </div>
            <div className="hidden sm:block text-xs text-muted-foreground">
              {stats.last_updated ? `Updated ${new Date(stats.last_updated).toLocaleString()}` : ""}
            </div>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-5 gap-2 sm:gap-3">
            <Card>
              <CardContent className="p-3 sm:p-4">
                <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Total</div>
                <div className="u-serif text-2xl sm:text-3xl font-semibold tabular-nums">{stats.total_articles.toLocaleString()}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-3 sm:p-4">
                <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">24h</div>
                <div className="u-serif text-2xl sm:text-3xl font-semibold tabular-nums">{stats.articles_last_24h.toLocaleString()}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-3 sm:p-4">
                <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Sources</div>
                <div className="u-serif text-2xl sm:text-3xl font-semibold tabular-nums">7</div>
                <div className="hidden sm:block text-xs text-muted-foreground mt-1">
                  GMA, Rappler, Inquirer, Manila Times, Philstar, Sunstar, Manila Bulletin
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-3 sm:p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Coverage (7d)</div>
                  <span
                    className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground"
                    title="Percent of last-7d articles that have rows in article_sentiment_public (public VADER sentiment cache)."
                    aria-label="Coverage info"
                  >
                    i
                  </span>
                </div>
                <div className="u-serif text-2xl sm:text-3xl font-semibold tabular-nums">
                  {typeof coveragePct === "number" ? `${coveragePct}%` : "—"}
                </div>
                <div className="mt-2 h-2 w-full rounded-full overflow-hidden border bg-muted" aria-label="Coverage progress bar">
                  <div className="h-full bg-accent" style={{ width: `${coveragePct ?? 0}%` }} />
                </div>
                <div className="hidden sm:block text-xs text-muted-foreground mt-1">Articles with VADER sentiment rows</div>
              </CardContent>
            </Card>

            <SentimentSplitCard
              positive={sentimentSplit.positive}
              neutral={sentimentSplit.neutral}
              negative={sentimentSplit.negative}
              unlabeled={sentimentSplit.unlabeled}
            />
          </div>
        </div>

        <LatestFeed articles={visibleArticles} limit={24} />

        <div className="space-y-8">
          <ArticleRowServer 
            articles={enrichedBySource["GMA"] || []} 
            title="GMA News" 
            sourceValue="GMA" 
            collapsible
          />
          <ArticleRowServer 
            articles={enrichedBySource["Rappler"] || []} 
            title="Rappler" 
            sourceValue="Rappler" 
            collapsible
          />
          <ArticleRowServer 
            articles={enrichedBySource["Inquirer"] || []} 
            title="Inquirer" 
            sourceValue="Inquirer" 
            collapsible
          />
          <ArticleRowServer 
            articles={enrichedBySource["Manila Times"] || []} 
            title="Manila Times" 
            sourceValue="Manila Times"
            collapsible
          />
          <ArticleRowServer 
            articles={enrichedBySource["Philstar"] || []} 
            title="Philstar" 
            sourceValue="Philstar" 
            collapsible
          />
          <ArticleRowServer 
            articles={enrichedBySource["Sunstar"] || []} 
            title="Sunstar" 
            sourceValue="Sunstar" 
            collapsible
          />
          <ArticleRowServer 
            articles={enrichedBySource["Manila Bulletin"] || []} 
            title="Manila Bulletin" 
            sourceValue="Manila Bulletin" 
            collapsible
          />
        </div>
      </div>
    </MainLayout>
  );
}
