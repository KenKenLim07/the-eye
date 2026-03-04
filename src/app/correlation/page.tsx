"use client";

import { useEffect, useState, useTransition, useCallback } from "react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, RefreshCw } from "lucide-react";

interface CorrelationData {
  ok: boolean;
  period: string;
  include_today: boolean;
  sources: string[];
  matrix: Array<Array<number | null>>;
  p_values: Array<Array<number | null>>;
  entities?: Array<{ text: string; type: string; mentions: number; avg_sentiment: number }>;
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

async function fetchCorrelation(period: string, source?: string, refresh = false): Promise<CorrelationData> {
  const base = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const params = new URLSearchParams({ period, include_today: "true", with_entities: "true" });
  if (source && source !== "all") params.set("sources", source);
  if (refresh) params.set("refresh", "true");

  const key = `corr:${period}:${source || "all"}:today:1:entities:1`;
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

  const load = useCallback(async (refresh = false) => {
    if (refresh) setRefreshing(true);
    else setLoading(true);
    const data = await fetchCorrelation(selectedPeriod, selectedSource !== "all" ? selectedSource : undefined, refresh);
    setCorr(data);
    setLoading(false);
    setRefreshing(false);
  }, [selectedPeriod, selectedSource]);

  useEffect(() => {
    load(false);
  }, [load]);

  return (
    <div className="container mx-auto max-w-6xl p-4">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Source Correlation</h1>
          <p className="text-muted-foreground">Pearson correlation of daily sentiment across sources</p>
        </div>

        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
          <div className="flex gap-4">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Source</label>
              <Select value={selectedSource} onValueChange={(v) => startTransition(() => setSelectedSource(v))} disabled={loading || isPending}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Select source" />
                </SelectTrigger>
                <SelectContent>
                  {SOURCES.map((s) => (
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

        <Card>
          <CardHeader>
            <CardTitle>Top Entities (NER + Sentiment)</CardTitle>
            <CardDescription>Entities extracted from the same correlation window</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-sm text-muted-foreground py-6">Loading entities...</div>
            ) : !corr?.entities || corr.entities.length === 0 ? (
              <div className="text-sm text-muted-foreground py-6">No entity data available.</div>
            ) : (
              <div className="overflow-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr>
                      <th className="text-left p-2">Entity</th>
                      <th className="text-left p-2">Type</th>
                      <th className="text-left p-2">Mentions</th>
                      <th className="text-left p-2">Avg Sentiment</th>
                    </tr>
                  </thead>
                  <tbody>
                    {corr.entities.map((e) => (
                      <tr key={`${e.text}:${e.type}`} className="border-t">
                        <td className="p-2">{e.text}</td>
                        <td className="p-2 text-muted-foreground">{e.type}</td>
                        <td className="p-2">{e.mentions}</td>
                        <td className="p-2">{e.avg_sentiment.toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
