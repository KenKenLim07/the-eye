"use client";

import { useEffect, useState, useTransition, useCallback } from "react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, RefreshCw } from "lucide-react";
import MainLayout from "@/components/layout/main-layout";
import { supabaseUntyped } from "@/lib/supabase/client";

interface CorrelationData {
  ok: boolean;
  period: string;
  include_today: boolean;
  sources: string[];
  matrix: Array<Array<number | null>>;
  p_values: Array<Array<number | null>>;
}

const SOURCES = [
  { value: "all", label: "All Sources" },
  { value: "GMA", label: "GMA" },
  { value: "Inquirer", label: "Inquirer" },
  { value: "Manila Bulletin", label: "Manila Bulletin" },
  { value: "Manila Times", label: "Manila Times" },
  { value: "Rappler", label: "Rappler" },
  { value: "Sunstar", label: "Sunstar" },
  { value: "Philstar", label: "Philstar" }
];

const PERIODS = [
  { value: "7d", label: "Last 7 Days" },
  { value: "30d", label: "Last 30 Days" }
];

const corrCache = new Map<string, { expires: number; data: CorrelationData }>();
const inflightRequests = new Map<string, Promise<CorrelationData>>();

function hasUsableBackend(): boolean {
  if (process.env.NODE_ENV === "development") return true;
  const url = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!url) return false;
  if (url.includes("localhost") || url.includes("127.0.0.1")) return false;
  return true;
}

function shouldUseSnapshots(): boolean {
  if (process.env.NEXT_PUBLIC_ANALYTICS_SOURCE === "supabase_snapshots") return true;
  return !hasUsableBackend();
}

function corrSnapshotKey(period: string): string {
  return `corr:period=${period}:sources=all:include_today=1`;
}

async function fetchCorrelationSnapshot(period: string): Promise<CorrelationData> {
  const key = corrSnapshotKey(period);
  const { data, error } = await supabaseUntyped
    .from("correlation_snapshots")
    .select("sources,matrix,p_values,period,include_today")
    .eq("key", key)
    .limit(1);
  if (error) throw error;
  const row = data?.[0];
  if (!row) return { ok: false, period, include_today: true, sources: [], matrix: [], p_values: [] };
  return {
    ok: true,
    period: row.period || period,
    include_today: row.include_today ?? true,
    sources: row.sources || [],
    matrix: row.matrix || [],
    p_values: row.p_values || [],
  } as CorrelationData;
}

async function fetchCorrelation(period: string, source?: string, refresh = false): Promise<CorrelationData> {
  if (shouldUseSnapshots()) {
    const key = `corr_snap:${period}:all`;
    const now = Date.now();
    const ttl = 60_000;
    if (!refresh) {
      const c = corrCache.get(key);
      if (c && c.expires > now) return c.data;
      const inflight = inflightRequests.get(key);
      if (inflight) return inflight;
    }
    const req = fetchCorrelationSnapshot(period)
      .then((json) => {
        corrCache.set(key, { expires: now + ttl, data: json });
        return json;
      })
      .finally(() => inflightRequests.delete(key));
    inflightRequests.set(key, req);
    return await req;
  }

  const base =
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
  if (!base || (process.env.NODE_ENV !== "development" && (base.includes("localhost") || base.includes("127.0.0.1")))) {
    return { ok: false, period, include_today: true, sources: [], matrix: [], p_values: [] } as CorrelationData;
  }
  const params = new URLSearchParams({ period, include_today: "true" });
  if (source && source !== "all") params.set("sources", source);
  if (refresh) params.set("refresh", "true");

  const key = `corr:${period}:${source || "all"}:today:1`;
  const now = Date.now();
  const ttl = 60_000;

  if (!refresh) {
    const c = corrCache.get(key);
    if (c && c.expires > now) return c.data;
    const inflight = inflightRequests.get(key);
    if (inflight) return inflight;
  }

  try {
    const req = fetch(`${base}/ml/correlation?${params}`, { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = (await res.json()) as CorrelationData;
        corrCache.set(key, { expires: now + ttl, data: json });
        return json;
      })
      .finally(() => inflightRequests.delete(key));

    inflightRequests.set(key, req);
    return await req;
  } catch (e) {
    console.error("Failed to fetch correlation:", e);
    return { ok: false, period, include_today: true, sources: [], matrix: [], p_values: [] } as CorrelationData;
  }
}

export default function CorrelationPage() {
  const [selectedSource, setSelectedSource] = useState("all");
  const [selectedPeriod, setSelectedPeriod] = useState("7d");
  const [corr, setCorr] = useState<CorrelationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [isPending, startTransition] = useTransition();
  const useSnapshots = shouldUseSnapshots();

  useEffect(() => {
    if (useSnapshots && selectedSource !== "all") setSelectedSource("all");
  }, [useSnapshots, selectedSource]);

  const load = useCallback(async (refresh = false) => {
    if (refresh) setRefreshing(true);
    else setLoading(true);
    const data = await fetchCorrelation(
      selectedPeriod,
      useSnapshots ? undefined : (selectedSource !== "all" ? selectedSource : undefined),
      refresh
    );
    setCorr(data);
    setLoading(false);
    setRefreshing(false);
  }, [selectedPeriod, selectedSource, useSnapshots]);

  useEffect(() => {
    load(false);
  }, [load]);

  return (
    <MainLayout containerSize="xl">
      <div className="space-y-6">
        <div>
          <h1 className="u-serif text-3xl font-semibold tracking-tight">Correlation Matrix</h1>
          <p className="text-muted-foreground">Daily average sentiment correlation across sources (last 7d/30d)</p>
        </div>

        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
          <div className="flex gap-4">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Source</label>
              <Select value={selectedSource} onValueChange={(v) => startTransition(() => setSelectedSource(v))} disabled={loading || isPending || useSnapshots}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Select source" />
                </SelectTrigger>
                <SelectContent>
                  {(useSnapshots ? SOURCES.slice(0, 1) : SOURCES).map((s) => (
                    <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Period</label>
              <Select value={selectedPeriod} onValueChange={(v) => startTransition(() => setSelectedPeriod(v))} disabled={loading || isPending}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Select period" />
                </SelectTrigger>
                <SelectContent>
                  {PERIODS.map((p) => (
                    <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button asChild variant="outline" size="sm"><Link href="/trends">Trends</Link></Button>
            <Button asChild variant="outline" size="sm"><Link href="/entities">Entity Ranking</Link></Button>
            <Button onClick={() => load(true)} variant="outline" size="sm" disabled={loading || refreshing}>
              {(loading || refreshing) ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
              Refresh
            </Button>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Correlation Matrix</CardTitle>
            <CardDescription>Daily average sentiment correlation across sources (last {selectedPeriod})</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-sm text-muted-foreground py-6">Loading correlation...</div>
            ) : !corr?.ok || (corr.sources?.length ?? 0) === 0 ? (
              <div className="text-sm text-muted-foreground py-6">No correlation data available.</div>
            ) : (
              <div className="overflow-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr>
                      <th className="text-left p-2">Source</th>
                      {corr.sources.map((s) => <th key={s} className="text-left p-2">{s}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {corr.sources.map((rowSrc, i) => (
                      <tr key={rowSrc} className="border-t">
                        <td className="p-2 font-medium">{rowSrc}</td>
                        {corr.sources.map((colSrc, j) => {
                          const r = corr.matrix[i]?.[j];
                          const p = corr.p_values[i]?.[j];
                          const bg = r == null ? "bg-gray-100" : r >= 0.5 ? "bg-green-100" : r <= -0.5 ? "bg-red-100" : "bg-yellow-50";
                          return (
                            <td key={colSrc} className={`p-2 ${bg}`} title={`r=${r == null ? "n/a" : r.toFixed(3)}${p != null ? `, p=${p.toFixed(3)}` : ""}`}>
                              {r == null ? "-" : r.toFixed(3)}
                            </td>
                          );
                        })}
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
