import MainLayout from "@/components/layout/main-layout";
import ArticleRowServer from "../components/articles/article-row-server";
import { fetchAllArticles, fetchLatestAnalysisByIds, fetchArticles } from "@/lib/articles";

// Cache the page for faster first load; refresh every 60s
export const revalidate = 60;

export default async function Home() {
  const t0 = Date.now();
  // Fetch latest articles per source using optimized single endpoint
  const PER_SOURCE_LIMIT = 10;
  const articlesBySource = await fetchAllArticles(PER_SOURCE_LIMIT);
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
  const normalizedBySource: Record<string, any[]> = Object.fromEntries(
    canonicalOrder.map((k) => [k, [] as any[]])
  );

  const allArticlesFlat: any[] = Object.values(articlesBySource).flat() as any[];
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
    .map((a: any) => Number(a.id))
    .filter(Boolean);

  // Fetch latest sentiment/bias analysis in one request (optional; non-fatal if fails)
  let analysisById: Record<number, any> = {};
  if (allArticleIds.length > 0) {
    try {
      analysisById = await fetchLatestAnalysisByIds(allArticleIds);
    } catch (err) {
      console.error("Failed to fetch analysis for home articles:", err);
    }
  }
  const tAfterAnalysis = Date.now();

  // Merge sentiment into articles before rendering
  const enrichedBySource: Record<string, any[]> = {};
  for (const [source, articles] of Object.entries(normalizedBySource)) {
    enrichedBySource[source] = (articles || []).map((article: any) => {
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
          <h1 className="text-3xl font-bold tracking-tight">Philippine News</h1>
          <p className="text-sm text-muted-foreground">Latest headlines aggregated from top PH news sources</p>
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
