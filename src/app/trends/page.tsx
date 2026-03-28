"use client";

import { useState, useEffect, useTransition, useCallback } from "react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RefreshCw, Loader2, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { Skeleton } from "@/components/ui/skeleton";
import MainLayout from "@/components/layout/main-layout";
import { supabaseUntyped } from "@/lib/supabase/client";
import AnalyticsFiltersSheet from "@/components/analytics/analytics-filters-sheet";
import ActiveFilters from "@/components/analytics/active-filters";
import { PH_SOURCES_WITH_ALL } from "@/lib/sources";

interface TrendsData {
  ok: boolean;
  computed_at?: string | null;
  summary: {
    period: string;
    source: string | null;
    total_articles: number;
    positive_pct: number;
    negative_pct: number;
    neutral_pct: number;
    avg_daily_articles: number;
  };
  timeline: Array<{
    date: string;
    positive: number;
    negative: number;
    neutral: number;
    total: number;
    avg_sentiment: number;
    positive_pct: number;
    negative_pct: number;
    neutral_pct: number;
  }>;
}

const SOURCES = PH_SOURCES_WITH_ALL;

const PERIODS = [
  { value: "7d", label: "Last 7 Days" },
  { value: "30d", label: "Last 30 Days" }
];

const COLORS = {
  positive: "#22c55e",
  negative: "#ef4444",
  neutral: "#6b7280"
};

const trendsCache = new Map<string, { expires: number; data: TrendsData }>();
const inflightRequests = new Map<string, Promise<TrendsData>>();

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

function trendsSnapshotKey(period: string): string {
  return `trends:period=${period}:source=all:include_today=1`;
}

async function fetchTrendsSnapshot(period: string): Promise<TrendsData> {
  const key = trendsSnapshotKey(period);
  const { data, error } = await supabaseUntyped
    .from("sentiment_trends_snapshots")
    .select("summary,timeline,computed_at")
    .eq("key", key)
    .limit(1);
  if (error) throw error;
  const row = data?.[0];
  if (!row) {
    return {
      ok: false,
      computed_at: null,
      summary: { period, source: null, total_articles: 0, positive_pct: 0, negative_pct: 0, neutral_pct: 0, avg_daily_articles: 0 },
      timeline: [],
    };
  }
  return { ok: true, computed_at: row.computed_at ?? null, summary: row.summary, timeline: row.timeline } as TrendsData;
}

async function fetchTrends(source?: string, period: string = "7d", opts?: { refresh?: boolean; ttlMs?: number }): Promise<TrendsData> {
  if (shouldUseSnapshots()) {
    const key = `trends_snap:${period}:all`;
    const now = Date.now();
    const ttl = opts?.ttlMs ?? 60_000;

    if (!opts?.refresh) {
      const cached = trendsCache.get(key);
      if (cached && cached.expires > now) return cached.data;
      const inflight = inflightRequests.get(key);
      if (inflight) return inflight;
    }

    const req = fetchTrendsSnapshot(period)
      .then((d) => {
        trendsCache.set(key, { expires: now + ttl, data: d });
        return d;
      })
      .finally(() => inflightRequests.delete(key));

    inflightRequests.set(key, req);
    return await req;
  }

  const base =
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
  if (!base || (process.env.NODE_ENV !== "development" && (base.includes("localhost") || base.includes("127.0.0.1")))) {
    return {
      ok: false,
      summary: {
        period,
        source: source || null,
        total_articles: 0,
        positive_pct: 0,
        negative_pct: 0,
        neutral_pct: 0,
        avg_daily_articles: 0,
      },
      timeline: [],
    };
  }
  const params = new URLSearchParams({ period, include_today: "true" });
  if (source && source !== "all") params.set("source", source);
  if (opts?.refresh) params.set("refresh", "true");
  const key = `trends:${period}:${source || "all"}:today:1`;
  const now = Date.now();
  const ttl = opts?.ttlMs ?? 60_000;

  if (!opts?.refresh) {
    const cached = trendsCache.get(key);
    if (cached && cached.expires > now) return cached.data;
    const inflight = inflightRequests.get(key);
    if (inflight) return inflight;
  }

  try {
    const req = fetch(`${base}/ml/trends?${params}`, { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        trendsCache.set(key, { expires: now + ttl, data: json });
        return json as TrendsData;
      })
      .finally(() => inflightRequests.delete(key));

    inflightRequests.set(key, req);
    return await req;
  } catch (error) {
    console.error("Failed to fetch trends:", error);
    return {
      ok: false,
      summary: {
        period,
        source: source || null,
        total_articles: 0,
        positive_pct: 0,
        negative_pct: 0,
        neutral_pct: 0,
        avg_daily_articles: 0
      },
      timeline: []
    };
  }
}

const SummaryCardSkeleton = () => (
  <Card>
    <CardHeader className="pb-2">
      <Skeleton className="h-4 w-24" />
    </CardHeader>
    <CardContent>
      <Skeleton className="h-8 w-16 mb-2" />
      <Skeleton className="h-3 w-20" />
    </CardContent>
  </Card>
);

const ChartSkeleton = () => (
  <Card>
    <CardHeader>
      <Skeleton className="h-6 w-48 mb-2" />
      <Skeleton className="h-4 w-64" />
    </CardHeader>
    <CardContent>
      <div className="h-96 flex items-center justify-center">
        <div className="flex items-center space-x-2">
          <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
          <span className="text-muted-foreground">Loading chart data...</span>
        </div>
      </div>
    </CardContent>
  </Card>
);

const TimelineSkeleton = () => (
  <Card>
    <CardHeader>
      <Skeleton className="h-6 w-48 mb-2" />
      <Skeleton className="h-4 w-64" />
    </CardHeader>
    <CardContent>
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="border rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <Skeleton className="h-5 w-24" />
              <Skeleton className="h-6 w-16" />
            </div>
            <Skeleton className="h-4 w-full mb-2" />
            <div className="flex gap-4">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-32" />
            </div>
          </div>
        ))}
      </div>
    </CardContent>
  </Card>
);

export default function TrendsPage() {
  const [data, setData] = useState<TrendsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedSource, setSelectedSource] = useState("all");
  const [selectedPeriod, setSelectedPeriod] = useState("7d");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isFilterLoading, setIsFilterLoading] = useState(false);
  const [, startTransition] = useTransition();
  const useSnapshots = shouldUseSnapshots();

  useEffect(() => {
    if (useSnapshots && selectedSource !== "all") setSelectedSource("all");
  }, [useSnapshots, selectedSource]);

  const loadData = useCallback(async (showRefreshIndicator = false, forceRefresh = false) => {
    if (showRefreshIndicator) {
      setIsRefreshing(true);
    } else if (!data) {
      setLoading(true);
    } else {
      setIsFilterLoading(true);
    }

    try {
      const trendsData = await fetchTrends(
        useSnapshots ? undefined : (selectedSource !== "all" ? selectedSource : undefined),
        selectedPeriod,
        { refresh: forceRefresh, ttlMs: 120_000 }
      );
      setData(trendsData);
      const computedAt = trendsData.computed_at;
      setLastUpdated(computedAt ? new Date(computedAt) : new Date());
    } catch (error) {
      console.error("Failed to load trends:", error);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
      setIsFilterLoading(false);
    }
  }, [data, selectedSource, selectedPeriod, useSnapshots]);

  const handleSourceChange = (newSource: string) => {
    setIsFilterLoading(true);
    startTransition(() => setSelectedSource(newSource));
  };

  const handlePeriodChange = (newPeriod: string) => {
    setIsFilterLoading(true);
    startTransition(() => setSelectedPeriod(newPeriod));
  };

  const handleRefresh = () => {
    loadData(true, true);
  };

  useEffect(() => {
    loadData(false, false);
  }, [loadData]);

  useEffect(() => {
    const interval = setInterval(() => loadData(true), 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [loadData]);

  if (loading && !data) {
    return (
      <MainLayout containerSize="xl">
        <div className="space-y-6">
          <div>
            <Skeleton className="h-8 w-64 mb-2" />
            <Skeleton className="h-4 w-96" />
          </div>

          <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
            <div className="flex gap-4">
              <div className="flex flex-col gap-2">
                <Skeleton className="h-4 w-12" />
                <Skeleton className="h-10 w-[180px]" />
              </div>
              <div className="flex flex-col gap-2">
                <Skeleton className="h-4 w-12" />
                <Skeleton className="h-10 w-[180px]" />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Skeleton className="h-9 w-20" />
              <Skeleton className="h-4 w-32" />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <SummaryCardSkeleton key={i} />
            ))}
          </div>

          <ChartSkeleton />
          <TimelineSkeleton />
        </div>
      </MainLayout>
    );
  }

  if (!data?.ok) {
    if (useSnapshots && selectedPeriod === "30d") {
      return (
        <MainLayout containerSize="xl">
          <div className="space-y-6">
            <div>
              <h1 className="u-serif text-3xl font-semibold tracking-tight">News Sentiment Trends</h1>
              <p className="text-muted-foreground">Analyzing sentiment patterns across Philippine news sources</p>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>30d snapshots aren’t generated yet</CardTitle>
                <CardDescription>
                  This deployment is using Supabase snapshot mode. Only 7d snapshots are currently automated by cron.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col sm:flex-row gap-2">
                <Button onClick={() => handlePeriodChange("7d")} className="h-11">
                  Switch to 7d
                </Button>
                <Button onClick={handleRefresh} variant="outline" className="h-11" disabled={isRefreshing}>
                  {isRefreshing ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4 mr-2" />
                  )}
                  Retry
                </Button>
              </CardContent>
            </Card>
          </div>
        </MainLayout>
      );
    }

    return (
      <div className="container mx-auto max-w-6xl p-4">
        <h1 className="text-3xl font-bold mb-6">News Sentiment Trends</h1>
        <Card>
          <CardContent className="p-6">
            <p className="text-muted-foreground">Failed to load trends data. Please try again later.</p>
            <Button onClick={handleRefresh} className="mt-4" disabled={isRefreshing}>
              {isRefreshing ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const { summary, timeline } = data;

  const chartData = timeline.map((day) => ({
    ...day,
    date: new Date(day.date).toLocaleDateString("en-US", { month: "short", day: "numeric" })
  }));

  const getSentimentIcon = (type: "positive" | "negative" | "neutral") => {
    switch (type) {
      case "positive":
        return <TrendingUp className="h-4 w-4" />;
      case "negative":
        return <TrendingDown className="h-4 w-4" />;
      case "neutral":
        return <Minus className="h-4 w-4" />;
    }
  };

  return (
    <MainLayout containerSize="xl">
      <div className="space-y-6">
        <div>
          <h1 className="u-serif text-3xl font-semibold tracking-tight">News Sentiment Trends</h1>
          <p className="text-muted-foreground">Analyzing sentiment patterns across Philippine news sources</p>
        </div>

        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
            <div className="hidden sm:grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Source</label>
                <Select value={selectedSource} onValueChange={handleSourceChange} disabled={isFilterLoading || useSnapshots}>
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Select source" />
                  </SelectTrigger>
                  <SelectContent>
                    {(useSnapshots ? SOURCES.slice(0, 1) : SOURCES).map((source) => (
                      <SelectItem key={source.value} value={source.value}>
                        {source.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium">Period</label>
                <Select value={selectedPeriod} onValueChange={handlePeriodChange} disabled={isFilterLoading}>
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Select period" />
                  </SelectTrigger>
                  <SelectContent>
                    {PERIODS.map((period) => (
                      <SelectItem key={period.value} value={period.value}>
                        {period.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 justify-start sm:justify-end w-full sm:w-auto">
              <div className="sm:hidden">
                <AnalyticsFiltersSheet
                  title="Trend filters"
                  source={selectedSource}
                  period={selectedPeriod}
                  sources={useSnapshots ? SOURCES.slice(0, 1) : SOURCES}
                  periods={PERIODS}
                  disableSource={useSnapshots}
                  onApply={({ source, period }) => {
                    handleSourceChange(source);
                    handlePeriodChange(period);
                  }}
                />
              </div>

              <Button asChild variant="outline" className="h-11">
                <Link href="/correlation">Correlation</Link>
              </Button>
              <Button asChild variant="outline" className="h-11">
                <Link href="/entities">Entities</Link>
              </Button>
              <Button onClick={handleRefresh} variant="outline" className="h-11" disabled={isRefreshing || isFilterLoading}>
                {(isRefreshing || isFilterLoading) ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4 mr-2" />
                )}
                Refresh
              </Button>
            </div>
          </div>

          <div className="sm:hidden space-y-2">
            <ActiveFilters
              items={[
                { label: "source", value: (SOURCES.find((s) => s.value === selectedSource)?.label ?? selectedSource) },
                { label: "period", value: (PERIODS.find((p) => p.value === selectedPeriod)?.label ?? selectedPeriod) },
                ...(lastUpdated
                  ? [{ label: "updated", value: lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) }]
                  : []),
              ]}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className={`transition-all duration-500 ${isFilterLoading ? "opacity-50 scale-98" : "opacity-100 scale-100"}`}>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Total Articles</CardTitle></CardHeader>
            <CardContent>
              <div className="text-2xl font-bold transition-all duration-700 ease-out">{summary.total_articles}</div>
              <p className="text-xs text-muted-foreground">Last {summary.period}</p>
            </CardContent>
          </Card>

          <Card className={`transition-all duration-500 ${isFilterLoading ? "opacity-50 scale-98" : "opacity-100 scale-100"}`}>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium flex items-center gap-2">{getSentimentIcon("positive")}Positive</CardTitle></CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600 transition-all duration-700 ease-out">{summary.positive_pct}%</div>
              <p className="text-xs text-muted-foreground">Positive sentiment</p>
            </CardContent>
          </Card>

          <Card className={`transition-all duration-500 ${isFilterLoading ? "opacity-50 scale-98" : "opacity-100 scale-100"}`}>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium flex items-center gap-2">{getSentimentIcon("negative")}Negative</CardTitle></CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600 transition-all duration-700 ease-out">{summary.negative_pct}%</div>
              <p className="text-xs text-muted-foreground">Negative sentiment</p>
            </CardContent>
          </Card>

          <Card className={`transition-all duration-500 ${isFilterLoading ? "opacity-50 scale-98" : "opacity-100 scale-100"}`}>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Daily Average</CardTitle></CardHeader>
            <CardContent>
              <div className="text-2xl font-bold transition-all duration-700 ease-out">{summary.avg_daily_articles}</div>
              <p className="text-xs text-muted-foreground">Articles per day</p>
            </CardContent>
          </Card>
        </div>

        <Card className={`transition-all duration-500 ${isFilterLoading ? "opacity-50" : "opacity-100"}`}>
          <CardHeader>
            <CardTitle>Sentiment Trends Over Time</CardTitle>
            <CardDescription>Daily sentiment distribution showing trends and patterns</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-96">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="positive" stroke={COLORS.positive} strokeWidth={3} name="Positive" dot={{ fill: COLORS.positive, strokeWidth: 2, r: 3 }} activeDot={{ r: 4 }} connectNulls />
                  <Line type="monotone" dataKey="negative" stroke={COLORS.negative} strokeWidth={3} name="Negative" dot={{ fill: COLORS.negative, strokeWidth: 2, r: 3 }} activeDot={{ r: 4 }} connectNulls />
                  <Line type="monotone" dataKey="neutral" stroke={COLORS.neutral} strokeWidth={3} name="Neutral" dot={{ fill: COLORS.neutral, strokeWidth: 2, r: 3 }} activeDot={{ r: 4 }} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card className={`transition-all duration-500 ${isFilterLoading ? "opacity-50" : "opacity-100"}`}>
          <CardHeader>
            <CardTitle>Daily Sentiment Timeline</CardTitle>
            <CardDescription>Sentiment distribution over the last {summary.period}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {timeline.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">No data available for the selected period and source.</p>
              ) : (
                timeline.map((day) => {
                  const analyzed = day.positive + day.neutral + day.negative;
                  const coveragePct = day.total > 0 ? ((analyzed / day.total) * 100).toFixed(1) : "0.0";
                  const total = Math.max(1, day.total);
                  const remainderCount = Math.max(0, total - analyzed);
                  const positiveWidth = (day.positive / total) * 100;
                  const neutralWidth = (day.neutral / total) * 100;
                  const negativeWidth = (day.negative / total) * 100;
                  const unscoredWidth = (remainderCount / total) * 100;
                  const remainderPct = day.total > 0 ? ((remainderCount / day.total) * 100).toFixed(1) : "0.0";

                  return (
                    <div key={day.date} className="border rounded-lg p-4 transition-all duration-500 hover:shadow-sm min-w-0">
                      <div className="flex items-center justify-between mb-2">
                        <div className="font-medium">{day.date}</div>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">{day.total} articles</Badge>
                          <Badge variant="secondary">Analyzed {analyzed}/{day.total} ({coveragePct}%)</Badge>
                        </div>
                      </div>

                      <div className="w-full h-3 mb-3 min-w-0 relative group" data-date={day.date}>
                        <div className="flex h-full rounded-full overflow-hidden shadow-sm">
                          {day.positive > 0 && <div className="bg-green-500 h-full" style={{ width: `${positiveWidth}%` }} />}
                          {day.neutral > 0 && <div className="bg-gray-500 h-full" style={{ width: `${neutralWidth}%` }} />}
                          {day.negative > 0 && <div className="bg-red-500 h-full" style={{ width: `${negativeWidth}%` }} />}
                          {remainderCount > 0 && <div className="bg-gray-300 h-full" style={{ width: `${unscoredWidth}%` }} />}
                        </div>
                      </div>

                      <div className="flex gap-4 text-sm text-muted-foreground">
                        <span className="text-green-600">Positive: {day.positive} ({day.positive_pct}%)</span>
                        <span className="text-gray-600">Neutral: {day.neutral} ({day.neutral_pct}%)</span>
                        <span className="text-red-600">Negative: {day.negative} ({day.negative_pct}%)</span>
                        {remainderCount > 0 && <span className="text-gray-500">Unscored: {remainderCount} ({remainderPct}%)</span>}
                        <span>Avg Score: {day.avg_sentiment.toFixed ? day.avg_sentiment.toFixed(3) : day.avg_sentiment}</span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}
