import MainLayout from "@/components/layout/main-layout";
import ArticleRowServer from "@/components/articles/article-row-server";
import { fetchAllArticles, fetchLatestAnalysisByIds } from "@/lib/articles";
import type { AnalysisRow, Article } from "@/lib/types";
import { supabaseServer, supabaseServerUntyped } from "@/lib/supabase/server";
import Link from "next/link";
import HomeControlBar from "@/components/home/control-bar";
import LatestFeed from "@/components/home/latest-feed";
import { formatDateTime } from "@/lib/utils/date";
import HomeKpis from "@/components/home/home-kpis";
import { unstable_cache } from "next/cache";
import { PH_SOURCES } from "@/lib/sources";

// In production we often run without a deployed backend; force dynamic so Supabase reads happen at request-time
// instead of being snapshotted during build (which can result in a "blank" homepage until the next revalidate).
export const dynamic = "force-dynamic";

type HomeStats = {
  total_articles: number;
  articles_last_24h: number;
  articles_last_7d: number;
  last_updated: string | null;
  coverage_7d: number | null; // 0..1, null when unavailable
  sentiment_7d: { positive: number; neutral: number; negative: number; unlabeled: number; total: number } | null;
};

async function fetchHomeArticlesFromSupabase(limitPerSource: number): Promise<Record<string, Article[]>> {
  const sources = [...PH_SOURCES];

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

async function fetchSentimentSplitFromSupabase(
  isoSince: string,
  hardCap: number
): Promise<{ positive: number; neutral: number; negative: number; unlabeled: number; total: number } | null> {
  try {
    const pageSize = 1000;
    let offset = 0;
    const ids: number[] = [];

    while (true) {
      const { data, error } = await supabaseServer
        .from("articles")
        .select("id")
        .gte("published_at", isoSince)
        .order("published_at", { ascending: false })
        .range(offset, offset + pageSize - 1);

      if (error) throw error;
      const rows = ((data as unknown) as Array<{ id: number }> | null) || [];
      for (const r of rows) {
        const id = Number(r.id);
        if (Number.isFinite(id)) ids.push(id);
      }
      if (rows.length < pageSize) break;
      offset += pageSize;
      if (ids.length >= hardCap) break;
    }

    if (ids.length === 0) return { positive: 0, neutral: 0, negative: 0, unlabeled: 0, total: 0 };

    const labelById = new Map<number, string | null>();
    const batchSize = 500;
    for (let i = 0; i < ids.length; i += batchSize) {
      const batch = ids.slice(i, i + batchSize);
      const { data: srows, error: serr } = await supabaseServerUntyped
        .from("article_sentiment_public")
        .select("article_id,sentiment_label")
        .in("article_id", batch);
      if (serr) throw serr;
      for (const r of (srows as Array<{ article_id: number; sentiment_label: string | null }> | null) || []) {
        labelById.set(Number(r.article_id), (r.sentiment_label as string | null | undefined) ?? null);
      }
    }

    let positive = 0;
    let neutral = 0;
    let negative = 0;
    let unlabeled = 0;

    for (const id of ids) {
      const label = (labelById.get(id) || "").toLowerCase();
      if (label === "positive") positive += 1;
      else if (label === "neutral") neutral += 1;
      else if (label === "negative") negative += 1;
      else unlabeled += 1;
    }

    return { positive, neutral, negative, unlabeled, total: ids.length };
  } catch (e) {
    console.warn("Failed to compute 7d sentiment split:", e);
    return null;
  }
}

async function fetchSentimentSplitFromTrendsSnapshot(
  period: "7d" | "30d"
): Promise<{ positive: number; neutral: number; negative: number; unlabeled: number; total: number } | null> {
  try {
    const key = `trends:period=${period}:source=all:include_today=1`;
    const { data, error } = await supabaseServerUntyped
      .from("sentiment_trends_snapshots")
      .select("timeline")
      .eq("key", key)
      .limit(1);
    if (error) throw error;
    const row = (data as Array<{ timeline?: unknown }> | null)?.[0];
    const timeline = (row as { timeline?: Array<Record<string, unknown>> } | undefined)?.timeline;
    if (!Array.isArray(timeline) || timeline.length === 0) return null;

    let positive = 0;
    let neutral = 0;
    let negative = 0;
    let total = 0;
    for (const day of timeline) {
      positive += Number(day?.positive ?? 0) || 0;
      neutral += Number(day?.neutral ?? 0) || 0;
      negative += Number(day?.negative ?? 0) || 0;
      total += Number(day?.total ?? 0) || 0;
    }
    const unlabeled = Math.max(0, total - positive - neutral - negative);
    return { positive, neutral, negative, unlabeled, total };
  } catch (e) {
    console.warn("Failed to read trends snapshot for sentiment split:", e);
    return null;
  }
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
    // For “freshness”, prefer ingestion time over source-reported publish time.
    supabaseServer.from("articles").select("inserted_at").order("inserted_at", { ascending: false }).limit(1),
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
  const last_updated = (lastUpdatedRes.data?.[0]?.inserted_at as string | null | undefined) ?? null;

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

  // Weekly sentiment split is used on the home KPI.
  // Prefer a DB-precomputed snapshot (fast + stable for Vercel demos), otherwise compute from the public cache table.
  const sentiment_7d =
    (await fetchSentimentSplitFromSupabase(iso7d, 12_000)) ??
    (await fetchSentimentSplitFromTrendsSnapshot("7d"));
  return {
    total_articles,
    articles_last_24h,
    articles_last_7d: typeof articles_last_7d === "number" ? articles_last_7d : 0,
    last_updated,
    coverage_7d,
    sentiment_7d,
  };
}

const fetchHomeStatsCached = unstable_cache(fetchHomeStatsFromSupabase, ["home-stats-v1"], { revalidate: 30 });
const fetchHomeArticlesCached = unstable_cache(
  async (limitPerSource: number, hasBackend: boolean) => {
    if (hasBackend) return fetchAllArticles(limitPerSource);
    return fetchHomeArticlesFromSupabase(limitPerSource);
  },
  ["home-articles-v1"],
  { revalidate: 15 }
);

export default async function Home() {
  const t0 = Date.now();
  const stats = await fetchHomeStatsCached().catch((e) => {
    console.error("Home stats fetch failed:", e);
    return { total_articles: 0, articles_last_24h: 0, articles_last_7d: 0, last_updated: null, coverage_7d: null, sentiment_7d: null } as HomeStats;
  });

  // Fetch latest articles per source using optimized single endpoint
  const PER_SOURCE_LIMIT = 10;
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "";
  const hasBackend =
    !!backendUrl &&
    (process.env.NODE_ENV === "development" ||
      (!backendUrl.includes("localhost") && !backendUrl.includes("127.0.0.1")));
  const articlesBySource = await fetchHomeArticlesCached(PER_SOURCE_LIMIT, hasBackend);
  const tAfterOptimized = Date.now();

  // Normalize backend source keys to canonical labels used in UI
  // Homepage source order (chips + KPI source list + per-source rows) is driven by PH_SOURCES.
  // Update src/lib/sources.ts to change the homepage order in one place.
  const canonicalOrder: string[] = [...PH_SOURCES];

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
    "ABS-CBN": ["abscbn", "abscbnnews", "abscbncom", "newsabscbn"],
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
  const sentimentSplitVisible = visibleArticles.reduce(
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

  const sentimentSplit7d = stats.sentiment_7d;
  const sentimentForCard = sentimentSplit7d ?? { ...sentimentSplitVisible, total: visibleArticles.length };
  const sentimentLabel = sentimentSplit7d ? "Sentiment (7d)" : "Sentiment (visible)";
  const sentimentSublabel = sentimentSplit7d
    ? `Last 7d: ${stats.articles_last_7d}`
    : `Sample: ${PER_SOURCE_LIMIT}×${canonicalOrder.length} = ${PER_SOURCE_LIMIT * canonicalOrder.length}`;

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
      <div className="space-y-8">
        <header>
          <h1 className="u-serif text-4xl sm:text-6xl font-bold tracking-tight leading-[1.02]">
            Today in the Philippines
          </h1>
          <p className="text-sm sm:text-base text-muted-foreground mt-2 max-w-prose">
            Headlines from top PH news sources—updated continuously, with sentiment and trends.
          </p>
        </header>

        <div>
          <HomeControlBar sources={canonicalOrder} lastUpdated={stats.last_updated} />
          <div className="text-xs text-muted-foreground mt-2">
            Tip: use <Link className="underline" href="/search">Advanced search</Link> for pagination.
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-end justify-between gap-3">
            <div className="space-y-1">
              <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Snapshot</div>
              <div className="font-sans text-xl sm:text-2xl font-semibold tracking-tight">Today’s pulse</div>
              <div className="sm:hidden text-xs text-muted-foreground">
                {stats.last_updated ? `Updated ${formatDateTime(stats.last_updated)}` : ""}
              </div>
            </div>
            <div className="hidden sm:block text-xs text-muted-foreground">
              {stats.last_updated ? `Updated ${formatDateTime(stats.last_updated)}` : ""}
            </div>
          </div>

          <HomeKpis
            totalArticles={stats.total_articles}
            articles24h={stats.articles_last_24h}
            coveragePct={typeof coveragePct === "number" ? coveragePct : null}
            sentiment={{
              label: sentimentLabel,
              sublabel: sentimentSublabel,
              positive: sentimentForCard.positive,
              neutral: sentimentForCard.neutral,
              negative: sentimentForCard.negative,
              unlabeled: sentimentForCard.unlabeled,
            }}
            sources={canonicalOrder}
          />
        </div>

        <div>
          <LatestFeed articles={visibleArticles} limit={15} />
        </div>

        <div className="space-y-8">
          {canonicalOrder.map((source) => (
            <ArticleRowServer
              key={source}
              articles={enrichedBySource[source] || []}
              title={source === "GMA" ? "GMA News" : source}
              sourceValue={source}
              collapsible
            />
          ))}
        </div>
      </div>
    </MainLayout>
  );
}
