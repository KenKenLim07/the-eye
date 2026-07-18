/** Shared live-API vs Supabase-snapshot mode for analytics pages. */

export function hasUsableBackend(): boolean {
  // Local `npm run dev` still prefers a running FastAPI unless snapshots are forced.
  if (process.env.NODE_ENV === "development") {
    if (process.env.NEXT_PUBLIC_ANALYTICS_SOURCE === "supabase_snapshots") return false;
    return true;
  }

  const url = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!url) return false;
  if (url.includes("localhost") || url.includes("127.0.0.1")) return false;
  return true;
}

/** Portfolio / demo: force precomputed Supabase snapshots (no live workers needed). */
export function shouldUseSnapshots(): boolean {
  if (process.env.NEXT_PUBLIC_ANALYTICS_SOURCE === "supabase_snapshots") return true;
  return !hasUsableBackend();
}

export function isPortfolioDemoMode(): boolean {
  return process.env.NEXT_PUBLIC_ANALYTICS_SOURCE === "supabase_snapshots";
}
