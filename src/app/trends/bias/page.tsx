"use client";

import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RefreshCw } from "lucide-react";
import { ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, Legend, BarChart, Bar } from "recharts";

const COLORS: Record<string, string> = {
  pro_government: "#3b82f6",
  pro_opposition: "#ef4444",
  neutral: "#6b7280",
};

const PERIODS = [
  { value: "7", label: "Last 7 Days" },
  { value: "30", label: "Last 30 Days" },
  { value: "90", label: "Last 90 Days" },
];

interface BiasSummary {
  ok: boolean;
  daily_buckets: Array<{ date: string; pro_government: number; pro_opposition: number; neutral: number }>
  distribution: Record<string, number>;
  top_sources: Array<{ source: string; direction: string; count: number }>
  top_categories: Array<{ category: string; direction: string; count: number }>
  recent_examples: Array<{ article_id: number; title: string; source: string; category: string; direction: string; confidence_score?: number; created_at: string }>
  model_version?: string;
}

interface BiasArticleList {
  ok: boolean;
  items: Array<{ article_id: number; title: string; url: string; source: string; category: string; direction: string; confidence_score?: number; created_at: string }>
}

async function fetchBiasSummary(days: number): Promise<BiasSummary> {
  const base = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  try {
    const res = await fetch(`${base}/bias/summary?days=${days}`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.error("fetchBiasSummary error", e);
    return { ok: false, daily_buckets: [], distribution: {}, top_sources: [], top_categories: [], recent_examples: [] } as BiasSummary;
  }
}

async function fetchBiasArticles(direction?: string, limit: number = 20): Promise<BiasArticleList> {
  const base = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const q = new URLSearchParams();
  if (direction) q.set("direction", direction);
  q.set("limit", String(limit));
  try {
    const res = await fetch(`${base}/bias/articles?${q}`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.error("fetchBiasArticles error", e);
    return { ok: false, items: [] };
  }
}

export default function BiasTrendsPage() {
  const [days, setDays] = useState<string>("7");
  const [summary, setSummary] = useState<BiasSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [recent, setRecent] = useState<BiasArticleList | null>(null);

  const load = async () => {
    setLoading(true);
    const s = await fetchBiasSummary(Number(days));
    setSummary(s);
    const r = await fetchBiasArticles(undefined, 20);
    setRecent(r);
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, [days]);

  const chartData = useMemo(() => {
    return (summary?.daily_buckets || []).map(d => ({
      ...d,
      date: new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    }));
  }, [summary]);

  const distData = useMemo(() => {
    const d = summary?.distribution || {};
    return [
      { name: 'Pro-Gov', key: 'pro_government', value: d.pro_government || 0 },
      { name: 'Pro-Opp', key: 'pro_opposition', value: d.pro_opposition || 0 },
      { name: 'Neutral', key: 'neutral', value: d.neutral || 0 },
    ];
  }, [summary]);

  return (
    <div className="container mx-auto max-w-6xl p-4">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Political Bias Trends</h1>
          <p className="text-muted-foreground">Bias direction distribution and trends across Philippine news</p>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium">Period</label>
            <Select value={days} onValueChange={setDays}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Select period" />
              </SelectTrigger>
              <SelectContent>
                {PERIODS.map(p => (
                  <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button variant="secondary" onClick={load}>
            <RefreshCw className="h-4 w-4 mr-2" /> Refresh
          </Button>
        </div>

        {loading && (
          <div className="flex items-center justify-center h-48 text-muted-foreground">
            <RefreshCw className="h-4 w-4 animate-spin mr-2" /> Loading...
          </div>
        )}

        {!loading && summary?.ok && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Direction Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={distData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="value" name="Count" fill="#3b82f6" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Trend by Day</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={280}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="pro_government" name="Pro-Gov" stroke={COLORS.pro_government} strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="pro_opposition" name="Pro-Opp" stroke={COLORS.pro_opposition} strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="neutral" name="Neutral" stroke={COLORS.neutral} strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        )}

        {!loading && summary?.ok && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Top Sources by Direction</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {(summary.top_sources || []).slice(0, 12).map((row, idx) => (
                    <div key={idx} className="flex justify-between text-sm">
                      <span>{row.source} <span className="text-muted-foreground">({row.direction})</span></span>
                      <span className="font-medium">{row.count}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Top Categories by Direction</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {(summary.top_categories || []).slice(0, 12).map((row, idx) => (
                    <div key={idx} className="flex justify-between text-sm">
                      <span>{row.category} <span className="text-muted-foreground">({row.direction})</span></span>
                      <span className="font-medium">{row.count}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {!loading && recent?.ok && (
          <Card>
            <CardHeader>
              <CardTitle>Recent Examples</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="divide-y">
                {(summary?.recent_examples || []).map((it) => (
                  <a key={it.article_id} href={"/"} className="block py-3 hover:bg-muted/40 rounded transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="min-w-0 pr-4">
                        <div className="truncate font-medium">{it.title || `Article #${it.article_id}`}</div>
                        <div className="text-xs text-muted-foreground truncate">{it.source} • {it.category} • {new Date(it.created_at).toLocaleString()}</div>
                      </div>
                      <div className="text-xs px-2 py-1 rounded border" style={{ color: COLORS[it.direction] }}>{it.direction}</div>
                    </div>
                  </a>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
