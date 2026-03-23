import { NextResponse } from "next/server";
import { supabaseServerUntyped } from "@/lib/supabase/server";

function safeHost(url: string | undefined | null): string | null {
  if (!url) return null;
  try {
    return new URL(url).host;
  } catch {
    return null;
  }
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

export async function GET() {
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "";
  const now = Date.now();
  const iso7d = new Date(now - 7 * 24 * 60 * 60 * 1000).toISOString();

  let articles_last_7d: number | null = null;
  let sentiment_rows_last_7d: number | null = null;
  let coverage_7d: number | null = null;
  let coverage_error: string | null = null;

  try {
    const [articles7dRes, sentiment7dRes] = await Promise.all([
      supabaseServerUntyped.from("articles").select("id", { count: "exact", head: true }).gte("published_at", iso7d),
      supabaseServerUntyped
        .from("articles")
        .select("id, article_sentiment_public!inner(article_id)", { count: "exact", head: true })
        .gte("published_at", iso7d),
    ]);

    if (articles7dRes.error) throw articles7dRes.error;
    if (sentiment7dRes.error) throw sentiment7dRes.error;

    articles_last_7d = articles7dRes.count ?? null;
    sentiment_rows_last_7d = sentiment7dRes.count ?? null;

    if (typeof articles_last_7d === "number" && articles_last_7d > 0 && typeof sentiment_rows_last_7d === "number") {
      coverage_7d = Math.min(1, Math.max(0, sentiment_rows_last_7d / articles_last_7d));
    }
  } catch (e: unknown) {
    coverage_error = e instanceof Error ? e.message : String(e);
  }

  return NextResponse.json({
    node_env: process.env.NODE_ENV ?? null,
    next_public_supabase_url_host: safeHost(process.env.NEXT_PUBLIC_SUPABASE_URL),
    next_public_backend_url_host: safeHost(backendUrl),
    intl_supports_asia_manila: supportsManilaTZ(),
    now_utc: new Date().toISOString(),
    iso_7d_cutoff_utc: iso7d,
    articles_last_7d,
    sentiment_rows_last_7d,
    coverage_7d,
    coverage_error,
  });
}

