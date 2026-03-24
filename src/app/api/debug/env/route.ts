import { NextResponse } from "next/server";
import { supabaseServerUntyped } from "@/lib/supabase/server";

// Debug endpoint should always reflect current runtime + DB state (avoid edge caching surprises).
export const dynamic = "force-dynamic";

function safeHost(url: string | undefined | null): string | null {
  if (!url) return null;
  try {
    return new URL(url).host;
  } catch {
    return null;
  }
}

function hasExplicitTimeZone(ts: string | null | undefined): boolean {
  if (!ts) return false;
  const s = String(ts).trim();
  return /(Z|[+-]\d{2}:\d{2})$/.test(s);
}

function supportsManilaTZ(): boolean {
  try {
    // Throws in environments without full ICU / timezone data.
    new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Manila", year: "numeric" }).format(new Date());
    return true;
  } catch {
    return false;
  }
}

export async function GET(req: Request) {
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "";
  const now = Date.now();
  const iso7d = new Date(now - 7 * 24 * 60 * 60 * 1000).toISOString();

  let articles_last_7d: number | null = null;
  let sentiment_rows_last_7d: number | null = null;
  let coverage_7d: number | null = null;
  let coverage_error: string | null = null;

  let latest_article_id: number | null = null;
  let latest_article_published_at: string | null = null;
  let latest_article_inserted_at: string | null = null;
  let latest_article_updated_at: string | null = null;
  let latest_article_published_has_tz: boolean | null = null;
  let latest_article_inserted_has_tz: boolean | null = null;
  let latest_article_updated_has_tz: boolean | null = null;
  let latest_ingest_lag_seconds: number | null = null;

  try {
    const [articles7dRes, sentiment7dRes, latestRes] = await Promise.all([
      supabaseServerUntyped.from("articles").select("id", { count: "exact", head: true }).gte("published_at", iso7d),
      supabaseServerUntyped
        .from("articles")
        .select("id, article_sentiment_public!inner(article_id)", { count: "exact", head: true })
        .gte("published_at", iso7d),
      supabaseServerUntyped
        .from("articles")
        .select("id,published_at,inserted_at,updated_at")
        .order("inserted_at", { ascending: false })
        .limit(1),
    ]);

    if (articles7dRes.error) throw articles7dRes.error;
    if (sentiment7dRes.error) throw sentiment7dRes.error;
    if (latestRes.error) throw latestRes.error;

    articles_last_7d = articles7dRes.count ?? null;
    sentiment_rows_last_7d = sentiment7dRes.count ?? null;

    if (typeof articles_last_7d === "number" && articles_last_7d > 0 && typeof sentiment_rows_last_7d === "number") {
      coverage_7d = Math.min(1, Math.max(0, sentiment_rows_last_7d / articles_last_7d));
    }

    const latest = (latestRes.data?.[0] as unknown as {
      id?: number | string | null;
      published_at?: string | null;
      inserted_at?: string | null;
      updated_at?: string | null;
    }) || null;
    if (latest) {
      latest_article_id = typeof latest.id === "number" ? latest.id : Number(latest.id) || null;
      latest_article_published_at = (latest.published_at as string | null) ?? null;
      latest_article_inserted_at = (latest.inserted_at as string | null) ?? null;
      latest_article_updated_at = (latest.updated_at as string | null) ?? null;

      latest_article_published_has_tz = hasExplicitTimeZone(latest_article_published_at);
      latest_article_inserted_has_tz = hasExplicitTimeZone(latest_article_inserted_at);
      latest_article_updated_has_tz = hasExplicitTimeZone(latest_article_updated_at);

      try {
        const insertedMs = latest_article_inserted_at ? new Date(latest_article_inserted_at).getTime() : NaN;
        latest_ingest_lag_seconds = Number.isFinite(insertedMs) ? Math.max(0, Math.round((Date.now() - insertedMs) / 1000)) : null;
      } catch {
        latest_ingest_lag_seconds = null;
      }
    }
  } catch (e: unknown) {
    coverage_error = e instanceof Error ? e.message : String(e);
  }

  return NextResponse.json({
    node_env: process.env.NODE_ENV ?? null,
    vercel_git_commit_sha: process.env.VERCEL_GIT_COMMIT_SHA ?? null,
    vercel_deployment_id: process.env.VERCEL_DEPLOYMENT_ID ?? null,
    vercel_region: process.env.VERCEL_REGION ?? null,
    request_user_agent: req.headers.get("user-agent") ?? null,
    request_accept_language: req.headers.get("accept-language") ?? null,
    next_public_supabase_url_host: safeHost(process.env.NEXT_PUBLIC_SUPABASE_URL),
    next_public_backend_url_host: safeHost(backendUrl),
    intl_supports_asia_manila: supportsManilaTZ(),
    now_utc: new Date().toISOString(),
    iso_7d_cutoff_utc: iso7d,
    latest_article_id,
    latest_article_published_at,
    latest_article_inserted_at,
    latest_article_updated_at,
    latest_article_published_has_tz,
    latest_article_inserted_has_tz,
    latest_article_updated_has_tz,
    latest_ingest_lag_seconds,
    articles_last_7d,
    sentiment_rows_last_7d,
    coverage_7d,
    coverage_error,
  });
}
