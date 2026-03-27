"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import MainLayout from "@/components/layout/main-layout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, RefreshCw } from "lucide-react";
import { formatDateTime } from "@/lib/utils/date";
import { supabase } from "@/lib/supabase/client";
import AnalyticsFiltersSheet from "@/components/analytics/analytics-filters-sheet";
import ActiveFilters from "@/components/analytics/active-filters";
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";

interface NerEntity {
  text: string;
  type: string;
  mentions: number;
  avg_sentiment?: number | null;
}

interface NerSampleData {
  ok: boolean;
  sampled?: number;
  sample_cap?: number;
  total_cap?: number;
  total_available?: number;
  total_capped?: number;
  scan_mode?: string;
  computed_at?: string;
  top_entities: NerEntity[];
}

type SnapshotRow = {
  key: string;
  period: string | null;
  source: string | null;
  computed_at: string | null;
  sampled: number | null;
  limit_articles: number | null;
  total_cap: number | null;
  total_available: number | null;
  total_capped: number | null;
  scan_mode: string | null;
  max_entities: number | null;
};

const SOURCES = [
  { value: "all", label: "All Sources" },
  { value: "GMA", label: "GMA" },
  { value: "Inquirer", label: "Inquirer" },
  { value: "Manila Bulletin", label: "Manila Bulletin" },
  { value: "Manila Times", label: "Manila Times" },
  { value: "Rappler", label: "Rappler" },
  { value: "Sunstar", label: "Sunstar" },
  { value: "Philstar", label: "Philstar" },
];

const PERIODS = [
  { value: "7d", label: "Last 7 Days" },
  { value: "30d", label: "Last 30 Days" },
];

const MAX_ENTITIES_TO_SHOW = 50;

const cache = new Map<string, { expires: number; data: NerSampleData }>();
const inflight = new Map<string, Promise<NerSampleData>>();

const snapshotsCache = new Map<string, { expires: number; data: NerSampleData }>();
const snapshotsInflight = new Map<string, Promise<NerSampleData>>();

function hasUsableBackend(): boolean {
  // In dev, assume the backend is available at localhost (even if NEXT_PUBLIC_BACKEND_URL is unset).
  if (process.env.NODE_ENV === "development") return true;

  const url = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!url) return false;

  // Treat local-only URLs as "no backend" for hosted demos.
  if (url.includes("localhost") || url.includes("127.0.0.1")) return false;
  return true;
}

function shouldUseSnapshots(): boolean {
  // Opt-in override for demo mode.
  if (process.env.NEXT_PUBLIC_ANALYTICS_SOURCE === "supabase_snapshots") return true;
  return !hasUsableBackend();
}

function snapshotKeyFor(period: string): string {
  // Matches backend/scripts/entity_rankings_snapshot.py
  return `entities:period=${period}:source=all:include_today=1:scan=full:limit=0:cap=0:max=100`;
}

function snapshotKeyFallbacks(period: string): string[] {
  // Compatibility for older snapshots written before switching to "full/no-cap".
  return [
    snapshotKeyFor(period),
    `entities:period=${period}:source=all:include_today=1:scan=fast:limit=500:cap=1000:max=100`,
  ];
}

async function fetchTopEntities(period: string, source: string | undefined, scanProfile: "fast500" | "deep1000", refresh = false): Promise<NerSampleData> {
  const base = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  // Default to a full scan (no article cap) for entities ranking accuracy.
  // Backend supports limit_articles=0 and total_cap=0 as "no cap".
  const limitArticles = 0;
  const scanMode = "full";
  const params = new URLSearchParams({
    period,
    limit_articles: String(limitArticles),
    total_cap: "0",
    max_entities: String(MAX_ENTITIES_TO_SHOW),
    scan_mode: scanMode,
  });
  if (source && source !== "all") params.set("source", source);
  if (refresh) params.set("refresh", "true");
  const key = `entities:${period}:${source || "all"}:full`;
  const now = Date.now();
  const ttl = 60_000;

  if (!refresh) {
    const c = cache.get(key);
    if (c && c.expires > now) return c.data;
    const r = inflight.get(key);
    if (r) return r;
  }

  const req = fetch(`${base}/ml/entities/top?${params}`, { cache: "no-store" })
    .then(async (res) => {
      if (res.ok) {
        const json = await res.json();
        const data: NerSampleData = {
          ok: !!json?.ok,
          sampled: json?.sampled,
          sample_cap: json?.sample_cap,
          total_cap: json?.total_cap,
          total_available: json?.total_available,
          total_capped: json?.total_capped,
          scan_mode: json?.scan_mode,
          top_entities: Array.isArray(json?.top_entities) ? json.top_entities : [],
        };
        cache.set(key, { expires: now + ttl, data });
        return data;
      }

      // Backward-compat fallback when /ml/entities/top is unavailable (e.g., after backend rollback)
      if (res.status === 404) {
        const daysBack = period === "30d" ? 30 : 7;
        const legacyParams = new URLSearchParams({
          days_back: String(daysBack),
          limit: String(limitArticles),
        });
        if (source && source !== "all") legacyParams.set("source", source);
        if (refresh) legacyParams.set("refresh", "true");
        const legacyRes = await fetch(`${base}/ml/ner/sample?${legacyParams}`, { cache: "no-store" });
        if (!legacyRes.ok) throw new Error(`HTTP ${legacyRes.status}`);
        const legacyJson = await legacyRes.json();
        const legacyData: NerSampleData = {
          ok: !!legacyJson?.ok,
          sampled: legacyJson?.sampled,
          sample_cap: limitArticles,
          total_cap: limitArticles,
          total_available: legacyJson?.sampled,
          total_capped: legacyJson?.sampled,
          scan_mode: scanMode,
          top_entities: Array.isArray(legacyJson?.top_entities) ? legacyJson.top_entities : [],
        };
        cache.set(key, { expires: now + ttl, data: legacyData });
        return legacyData;
      }

      throw new Error(`HTTP ${res.status}`);
    })
    .catch((err) => {
      console.error("Failed to fetch entities:", err);
      return { ok: false, top_entities: [] };
    })
    .finally(() => inflight.delete(key));

  inflight.set(key, req);
  return req;
}

async function fetchTopEntitiesFromSnapshots(period: string, refresh = false): Promise<NerSampleData> {
  const key = `entities_snapshots:${period}:all`;
  const now = Date.now();
  const ttl = 60_000;

  if (!refresh) {
    const c = snapshotsCache.get(key);
    if (c && c.expires > now) return c.data;
    const r = snapshotsInflight.get(key);
    if (r) return r;
  }

  const req = (async () => {
    try {
      const keys = snapshotKeyFallbacks(period);
      let snap: SnapshotRow | null = null;

      for (const snapshotKey of keys) {
        const snapRes = await supabase
          .from("entity_rankings_snapshots")
          .select("key,period,source,computed_at,sampled,limit_articles,total_cap,total_available,total_capped,scan_mode,max_entities")
          .eq("key", snapshotKey)
          .maybeSingle();
        if (snapRes.error) {
          throw new Error(snapRes.error.message);
        }
        if (snapRes.data) {
          snap = snapRes.data;
          break;
        }
      }

      if (!snap) return { ok: false, top_entities: [] };

      const itemsRes = await supabase
        .from("entity_rankings_items")
        .select("entity_text,entity_type,mentions,avg_sentiment")
        .eq("snapshot_key", snap.key)
        .order("mentions", { ascending: false })
        .limit(MAX_ENTITIES_TO_SHOW);

      if (itemsRes.error) {
        throw new Error(itemsRes.error.message);
      }

      const data: NerSampleData = {
        ok: true,
        computed_at: snap.computed_at ?? undefined,
        sampled: typeof snap.sampled === "number" ? snap.sampled : 0,
        sample_cap:
          typeof snap.limit_articles === "number" && snap.limit_articles > 0
            ? snap.limit_articles
            : (typeof snap.total_capped === "number" ? snap.total_capped : 0),
        total_cap: typeof snap.total_cap === "number" ? snap.total_cap : 1000,
        total_available: typeof snap.total_available === "number" ? snap.total_available : undefined,
        total_capped: typeof snap.total_capped === "number" ? snap.total_capped : undefined,
        scan_mode: typeof snap.scan_mode === "string" ? snap.scan_mode : "fast",
        top_entities: Array.isArray(itemsRes.data)
          ? itemsRes.data.map((r) => ({
              text: String(r.entity_text ?? ""),
              type: String(r.entity_type ?? ""),
              mentions: Number(r.mentions ?? 0),
              avg_sentiment: r.avg_sentiment == null ? null : Number(r.avg_sentiment),
            }))
          : [],
      };

      snapshotsCache.set(key, { expires: now + ttl, data });
      return data;
    } catch (err) {
      console.error("Failed to fetch entity snapshots:", err);
      return { ok: false, top_entities: [] };
    } finally {
      snapshotsInflight.delete(key);
    }
  })();

  snapshotsInflight.set(key, req);
  return req;
}

export default function EntitiesPage() {
  const useSnapshots = shouldUseSnapshots();
  const [selectedSource, setSelectedSource] = useState("all");
  const [selectedPeriod, setSelectedPeriod] = useState("7d");
  const [rows, setRows] = useState<NerEntity[]>([]);
  const [sampled, setSampled] = useState<number>(0);
  const [sampleCap, setSampleCap] = useState<number>(500);
  const [totalCap, setTotalCap] = useState<number>(1000);
  const [totalAvailable, setTotalAvailable] = useState<number | null>(null);
  const [totalCapped, setTotalCapped] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [isPending, startTransition] = useTransition();
  const [computedAt, setComputedAt] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const visibleRows = rows.slice(0, MAX_ENTITIES_TO_SHOW);

  const sentimentTextClass = (v: number | null | undefined) => {
    if (typeof v !== "number") return "text-muted-foreground";
    if (v > 0.05) return "text-emerald-700 dark:text-emerald-300";
    if (v < -0.05) return "text-rose-700 dark:text-rose-300";
    return "text-muted-foreground";
  };

  const EntitiesTableSkeleton = () => (
    <div className="overflow-x-auto -mx-2 px-2 sm:mx-0 sm:px-0">
      <div className="rounded-lg border overflow-hidden">
        <div className="grid grid-cols-12 gap-2 p-3 bg-muted/20">
          <Skeleton className="h-3 col-span-2" />
          <Skeleton className="h-3 col-span-6" />
          <Skeleton className="h-3 col-span-2 hidden sm:block" />
          <Skeleton className="h-3 col-span-2" />
        </div>
        <div className="divide-y">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="grid grid-cols-12 gap-2 p-3">
              <Skeleton className="h-4 col-span-2" />
              <Skeleton className="h-4 col-span-6" />
              <Skeleton className="h-4 col-span-2 hidden sm:block" />
              <Skeleton className="h-4 col-span-2" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const load = useCallback(async (refresh = false) => {
    if (refresh) setRefreshing(true);
    else setLoading(true);
    setLoadError(null);
    const effectiveSource = useSnapshots ? "all" : selectedSource;
    let data: NerSampleData;
    try {
      data = useSnapshots
        ? await fetchTopEntitiesFromSnapshots(selectedPeriod, refresh)
        : await fetchTopEntities(selectedPeriod, effectiveSource !== "all" ? effectiveSource : undefined, "fast500", refresh);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Failed to load entities.");
      data = { ok: false, top_entities: [] };
    }
    setRows(data.top_entities || []);
    setSampled(data.sampled || 0);
    setSampleCap(data.sample_cap || 500);
    setTotalCap(data.total_cap || 1000);
    setTotalAvailable(typeof data.total_available === "number" ? data.total_available : null);
    setTotalCapped(typeof data.total_capped === "number" ? data.total_capped : null);
    setComputedAt(typeof data.computed_at === "string" ? data.computed_at : null);
    setLoading(false);
    setRefreshing(false);
  }, [selectedPeriod, selectedSource, useSnapshots]);

  useEffect(() => {
    load(false);
  }, [selectedSource, selectedPeriod, load]);

  useEffect(() => {
    if (useSnapshots) {
      setSelectedSource("all");
    }
  }, [useSnapshots]);

  return (
    <MainLayout containerSize="xl">
      <div className="space-y-6">
        <div>
          <h1 className="u-serif text-3xl font-semibold tracking-tight">Top Mentioned Entities</h1>
          <p className="text-muted-foreground">
            Top Entities (NER + Sentiment) extracted from recent articles.
          </p>
        </div>

        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
            <div className="hidden sm:grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Source</label>
                <Select
                  value={selectedSource}
                  onValueChange={(v) => startTransition(() => setSelectedSource(v))}
                  disabled={loading || isPending || useSnapshots}
                >
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Select source" />
                  </SelectTrigger>
                  <SelectContent>
                    {(useSnapshots ? SOURCES.slice(0, 1) : SOURCES).map((s) => (
                      <SelectItem key={s.value} value={s.value}>
                        {s.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Period</label>
                <Select
                  value={selectedPeriod}
                  onValueChange={(v) => startTransition(() => setSelectedPeriod(v))}
                  disabled={loading || isPending}
                >
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Select period" />
                  </SelectTrigger>
                  <SelectContent>
                    {PERIODS.map((p) => (
                      <SelectItem key={p.value} value={p.value}>
                        {p.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 justify-start sm:justify-end w-full sm:w-auto">
              <div className="sm:hidden">
                <AnalyticsFiltersSheet
                  title="Entity filters"
                  source={selectedSource}
                  period={selectedPeriod}
                  sources={useSnapshots ? SOURCES.slice(0, 1) : SOURCES}
                  periods={PERIODS}
                  disableSource={useSnapshots}
                  onApply={({ source, period }) => {
                    startTransition(() => setSelectedSource(source));
                    startTransition(() => setSelectedPeriod(period));
                  }}
                />
              </div>

              <Button asChild variant="outline" className="h-11">
                <Link href="/trends">Trends</Link>
              </Button>
              <Button asChild variant="outline" className="h-11">
                <Link href="/correlation">Correlation</Link>
              </Button>
              <Button onClick={() => load(true)} variant="outline" className="h-11" disabled={loading || refreshing}>
                {(loading || refreshing) ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
                Refresh
              </Button>
            </div>
          </div>

          <div className="sm:hidden space-y-2">
            <ActiveFilters
              items={[
                { label: "source", value: (SOURCES.find((s) => s.value === selectedSource)?.label ?? selectedSource) },
                { label: "period", value: (PERIODS.find((p) => p.value === selectedPeriod)?.label ?? selectedPeriod) },
                ...(computedAt ? [{ label: "snapshot", value: formatDateTime(computedAt) }] : []),
              ]}
            />
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Top {MAX_ENTITIES_TO_SHOW} Entities (NER + Sentiment)</CardTitle>
            <CardDescription className="break-words">
              {computedAt ? `Snapshot: ${formatDateTime(computedAt)}. ` : ""}
              Scanned: {sampleCap || 0} / {totalCapped ?? totalCap}
              {typeof totalAvailable === "number" ? ` (available: ${totalAvailable})` : ""} • Contributed (entities+sentiment): {sampled}
              {sampleCap > 0 && sampled >= sampleCap && (totalCapped ?? totalCap) > sampleCap ? `, capped at ${sampleCap}` : ""}
              {` • Top ${MAX_ENTITIES_TO_SHOW} by mentions`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <EntitiesTableSkeleton />
            ) : loadError ? (
              <div className="text-sm text-red-600 py-6 whitespace-pre-wrap break-words">
                {loadError}
              </div>
            ) : visibleRows.length === 0 ? (
              <div className="text-sm text-muted-foreground py-6">No entity data available for the selected filter.</div>
            ) : (
              <div className="overflow-x-auto -mx-2 px-2 sm:mx-0 sm:px-0">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-card/90 backdrop-blur border-b">
                    <tr>
                      <th className="text-left p-2 u-mono text-[10px] uppercase tracking-widest text-muted-foreground w-14">Rank</th>
                      <th className="text-left p-2 u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Entity</th>
                      <th className="hidden sm:table-cell text-left p-2 u-mono text-[10px] uppercase tracking-widest text-muted-foreground w-24">Type</th>
                      <th className="text-right p-2 u-mono text-[10px] uppercase tracking-widest text-muted-foreground w-24">Mentions</th>
                      <th className="hidden sm:table-cell text-right p-2 u-mono text-[10px] uppercase tracking-widest text-muted-foreground w-24">Avg</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleRows.map((e, idx) => (
                      <tr key={`${e.text}:${e.type}:${idx}`} className={`border-t ${idx % 2 === 0 ? "bg-transparent" : "bg-muted/30"}`}>
                        <td className="p-2 u-mono text-[11px] text-muted-foreground">{idx + 1}</td>
                        <td className="p-2 font-medium break-words">
                          <div>{e.text}</div>
                          <div className="sm:hidden mt-0.5 u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                            {e.type}
                          </div>
                          <div
                            className={[
                              "sm:hidden mt-0.5 u-mono text-[10px] uppercase tracking-widest",
                              sentimentTextClass(e.avg_sentiment),
                            ].join(" ")}
                            title="Average sentiment score (VADER compound, averaged over entity mentions)"
                          >
                            Avg {typeof e.avg_sentiment === "number" ? e.avg_sentiment.toFixed(3) : "-"}
                          </div>
                        </td>
                        <td className="hidden sm:table-cell p-2 text-muted-foreground u-mono text-[11px] uppercase tracking-widest">{e.type}</td>
                        <td className="p-2 text-right u-mono text-[11px]">{e.mentions}</td>
                        <td className={`hidden sm:table-cell p-2 text-right u-mono text-[11px] ${sentimentTextClass(e.avg_sentiment)}`}>
                          {typeof e.avg_sentiment === "number" ? e.avg_sentiment.toFixed(3) : "-"}
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
    </MainLayout>
  );
}
