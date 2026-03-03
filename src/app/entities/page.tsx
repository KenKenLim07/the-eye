"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import MainLayout from "@/components/layout/main-layout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, RefreshCw } from "lucide-react";

interface NerEntity {
  text: string;
  type: string;
  mentions: number;
}

interface NerSampleData {
  ok: boolean;
  sampled?: number;
  sample_cap?: number;
  total_cap?: number;
  total_available?: number;
  total_capped?: number;
  scan_mode?: string;
  top_entities: NerEntity[];
}

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

const cache = new Map<string, { expires: number; data: NerSampleData }>();
const inflight = new Map<string, Promise<NerSampleData>>();

async function fetchTopEntities(period: string, source: string | undefined, scanProfile: "fast500" | "deep1000", refresh = false): Promise<NerSampleData> {
  const base = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const limitArticles = scanProfile === "deep1000" ? 1000 : 500;
  const scanMode = scanProfile === "deep1000" ? "full" : "fast";
  const params = new URLSearchParams({
    period,
    limit_articles: String(limitArticles),
    total_cap: "1000",
    max_entities: "100",
    scan_mode: scanMode,
  });
  if (source && source !== "all") params.set("source", source);
  if (refresh) params.set("refresh", "true");
  const key = `entities:${period}:${source || "all"}:${scanProfile}`;
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

export default function EntitiesPage() {
  const [selectedSource, setSelectedSource] = useState("all");
  const [selectedPeriod, setSelectedPeriod] = useState("30d");
  const [rows, setRows] = useState<NerEntity[]>([]);
  const [sampled, setSampled] = useState<number>(0);
  const [sampleCap, setSampleCap] = useState<number>(500);
  const [totalCap, setTotalCap] = useState<number>(1000);
  const [totalAvailable, setTotalAvailable] = useState<number | null>(null);
  const [totalCapped, setTotalCapped] = useState<number | null>(null);
  const [scanProfile, setScanProfile] = useState<"fast500" | "deep1000">("fast500");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [isPending, startTransition] = useTransition();

  const load = useCallback(async (refresh = false) => {
    if (refresh) setRefreshing(true);
    else setLoading(true);
    const data = await fetchTopEntities(selectedPeriod, selectedSource !== "all" ? selectedSource : undefined, scanProfile, refresh);
    setRows(data.top_entities || []);
    setSampled(data.sampled || 0);
    setSampleCap(data.sample_cap || (scanProfile === "deep1000" ? 1000 : 500));
    setTotalCap(data.total_cap || 1000);
    setTotalAvailable(typeof data.total_available === "number" ? data.total_available : null);
    setTotalCapped(typeof data.total_capped === "number" ? data.total_capped : null);
    setLoading(false);
    setRefreshing(false);
  }, [selectedPeriod, selectedSource, scanProfile]);

  useEffect(() => {
    load(false);
  }, [selectedSource, selectedPeriod, scanProfile, load]);

  return (
    <MainLayout containerSize="xl">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Top Mentioned Entities</h1>
          <p className="text-muted-foreground">
            Frequency ranking of people, organizations, and places across Philippine news sources.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
          <div className="flex gap-4">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Source</label>
              <Select
                value={selectedSource}
                onValueChange={(v) => startTransition(() => setSelectedSource(v))}
                disabled={loading || isPending}
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Select source" />
                </SelectTrigger>
                <SelectContent>
                  {SOURCES.map((s) => (
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
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Scan</label>
              <Select
                value={scanProfile}
                onValueChange={(v) => startTransition(() => setScanProfile(v as "fast500" | "deep1000"))}
                disabled={loading || isPending}
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Select scan profile" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="fast500">Fast (500)</SelectItem>
                  <SelectItem value="deep1000">Deep (1000)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <Button onClick={() => load(true)} variant="outline" size="sm" disabled={loading || refreshing}>
            {(loading || refreshing) ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
            Refresh
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Entity Ranking</CardTitle>
            <CardDescription>
              Sampled: {sampled} / {totalCapped ?? totalCap}
              {typeof totalAvailable === "number" ? ` (available: ${totalAvailable})` : ""}
              {sampled >= sampleCap ? `, capped at ${sampleCap}` : ""}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-sm text-muted-foreground py-6">Loading entities...</div>
            ) : rows.length === 0 ? (
              <div className="text-sm text-muted-foreground py-6">No entity data available for the selected filter.</div>
            ) : (
              <div className="overflow-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr>
                      <th className="text-left p-2">Rank</th>
                      <th className="text-left p-2">Entity</th>
                      <th className="text-left p-2">Type</th>
                      <th className="text-left p-2">Mentions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.slice(0, 100).map((e, idx) => (
                      <tr key={`${e.text}:${e.type}:${idx}`} className="border-t">
                        <td className="p-2">{idx + 1}</td>
                        <td className="p-2 font-medium">{e.text}</td>
                        <td className="p-2 text-muted-foreground">{e.type}</td>
                        <td className="p-2">{e.mentions}</td>
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
