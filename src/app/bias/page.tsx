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
  { value: "1", label: "Last 24 Hours" },
  { value: "7", label: "Last 7 Days" },
  { value: "30", label: "Last 30 Days" },
];

interface BiasSummary {
  ok: boolean;
  daily_buckets: Array<{ date: string; total: number; by_direction: { neutral: number; pro_government: number; pro_opposition: number } }>
  distribution: Record<string, number>;
  top_sources: Array<{ source: string; count: number }>
  top_categories: Array<{ category: string; count: number }>
  recent_examples: Array<{ id: number; title: string; source: string; published_at: string }>
  model_version?: string;
}

interface BiasArticleList {
  ok: boolean;
  items: Array<{ id: number; article_id: number; model_metadata: { direction: string }; articles: { title: string; url: string; source: string; category: string; published_at: string }; created_at: string }>
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
    return { ok: false, items: [] } as BiasArticleList;
  }
}

export default function BiasTrendsPage() {
  const [summary, setSummary] = useState<BiasSummary | null>(null);
  const [articles, setArticles] = useState<BiasArticleList | null>(null);
  const [selectedPeriod, setSelectedPeriod] = useState("7");
  const [selectedDirection, setSelectedDirection] = useState<string | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isFilterLoading, setIsFilterLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const loadData = async (showRefreshIndicator = false) => {
    if (showRefreshIndicator) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    
    try {
      const [summaryData, articlesData] = await Promise.all([
        fetchBiasSummary(Number(selectedPeriod)),
        fetchBiasArticles(selectedDirection, 20)
      ]);
      setSummary(summaryData);
      setArticles(articlesData);
      setLastUpdated(new Date());
    } catch (error) {
      console.error("Error loading data:", error);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
      setIsFilterLoading(false);
    }
  };

  const handlePeriodChange = async (period: string) => {
    setIsFilterLoading(true);
    setSelectedPeriod(period);
  };

  const handleRefresh = async () => {
    loadData(true);
  };

  useEffect(() => {
    loadData();
  }, [selectedPeriod, selectedDirection]);

  const chartData = useMemo(() => {
    if (!summary?.daily_buckets) return [];
    return summary.daily_buckets.map(bucket => ({
      date: bucket.date,
      "Pro-Government": bucket.by_direction.pro_government || 0,
      "Pro-Opposition": bucket.by_direction.pro_opposition || 0,
      "Neutral": bucket.by_direction.neutral || 0,
    }));
  }, [summary]);

  const distributionData = useMemo(() => {
    if (!summary?.distribution) return [];
    return Object.entries(summary.distribution).map(([key, value]) => ({
      name: key.replace('_', '-'),
      value,
      color: COLORS[key] || '#6b7280'
    }));
  }, [summary]);

  if (isLoading && !summary) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center h-64">
          <div className="flex items-center gap-2">
            <RefreshCw className="h-4 w-4 animate-spin" />
            <span>Loading bias analysis...</span>
          </div>
        </div>
      </div>
    );
  }

  if (!summary?.ok) {
    return (
      <div className="container mx-auto p-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-600 mb-4">Error Loading Data</h1>
          <p className="text-gray-600 mb-4">Failed to load bias analysis data.</p>
          <Button onClick={() => loadData()}>
            Try Again
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Political Bias Analysis</h1>
        <div className="flex items-center gap-4">
          <Select value={selectedPeriod} onValueChange={handlePeriodChange} disabled={isFilterLoading}>
            <SelectTrigger className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PERIODS.map(period => (
                <SelectItem key={period.value} value={period.value}>
                  {period.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={isRefreshing || isFilterLoading}
          >
            <RefreshCw className={`h-4 w-4 ${(isRefreshing || isFilterLoading) ? 'animate-spin' : ''}`} />
          </Button>
          {lastUpdated && (
            <span className="text-xs text-muted-foreground">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Daily Sentiment Timeline Chart - Trends-style animation */}
        <Card className={`transition-all duration-500 ${isFilterLoading ? 'opacity-50' : 'opacity-100'}`}>
          <CardHeader>
            <CardTitle>Daily Sentiment Timeline</CardTitle>
            <p className="text-sm text-muted-foreground">
              Sentiment distribution over the last {selectedPeriod}d
            </p>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line 
                  type="monotone" 
                  dataKey="Pro-Government" 
                  stroke={COLORS.pro_government} 
                  strokeWidth={3}
                  dot={{ fill: COLORS.pro_government, strokeWidth: 2, r: 4 }}
                  animationDuration={isFilterLoading ? 0 : 1000}
                  animationEasing="ease-in-out"
                />
                <Line 
                  type="monotone" 
                  dataKey="Pro-Opposition" 
                  stroke={COLORS.pro_opposition} 
                  strokeWidth={3}
                  dot={{ fill: COLORS.pro_opposition, strokeWidth: 2, r: 4 }}
                  animationDuration={isFilterLoading ? 0 : 1000}
                  animationEasing="ease-in-out"
                />
                <Line 
                  type="monotone" 
                  dataKey="Neutral" 
                  stroke={COLORS.neutral} 
                  strokeWidth={3}
                  dot={{ fill: COLORS.neutral, strokeWidth: 2, r: 4 }}
                  animationDuration={isFilterLoading ? 0 : 1000}
                  animationEasing="ease-in-out"
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Overall Distribution Chart - Trends-style animation */}
        <Card className={`transition-all duration-500 ${isFilterLoading ? 'opacity-50' : 'opacity-100'}`}>
          <CardHeader>
            <CardTitle>Overall Distribution</CardTitle>
            <p className="text-sm text-muted-foreground">
              Total articles analyzed: {summary.daily_buckets.reduce((sum, bucket) => sum + bucket.total, 0)}
            </p>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={distributionData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar 
                  dataKey="value" 
                  fill="#8884d8"
                  animationDuration={isFilterLoading ? 0 : 1000}
                  animationEasing="ease-in-out"
                />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Summary Cards - Trends-style opacity/scale animation */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className={`transition-all duration-500 ${isFilterLoading ? 'opacity-50 scale-98' : 'opacity-100 scale-100'}`}>
          <CardHeader>
            <CardTitle>Top Sources</CardTitle>
            <p className="text-sm text-muted-foreground">
              Most active news sources
            </p>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {summary.top_sources.slice(0, 5).map((item, i) => (
                <div 
                  key={i} 
                  className="flex items-center justify-between transition-all duration-700 ease-out"
                  style={{
                    animationDelay: isFilterLoading ? '0ms' : `${i * 100}ms`,
                    animation: isFilterLoading ? 'none' : 'fadeInUp 0.8s ease-out forwards'
                  }}
                >
                  <span className="text-sm">{item.source}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600">
                      Source
                    </span>
                    <span className="text-sm font-medium">{item.count}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className={`transition-all duration-500 ${isFilterLoading ? 'opacity-50 scale-98' : 'opacity-100 scale-100'}`}>
          <CardHeader>
            <CardTitle>Top Categories</CardTitle>
            <p className="text-sm text-muted-foreground">
              Most discussed topics
            </p>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {summary.top_categories.slice(0, 5).map((item, i) => (
                <div 
                  key={i} 
                  className="flex items-center justify-between transition-all duration-700 ease-out"
                  style={{
                    animationDelay: isFilterLoading ? '0ms' : `${i * 100}ms`,
                    animation: isFilterLoading ? 'none' : 'fadeInUp 0.8s ease-out forwards'
                  }}
                >
                  <span className="text-sm">{item.category}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600">
                      Category
                    </span>
                    <span className="text-sm font-medium">{item.count}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className={`transition-all duration-500 ${isFilterLoading ? 'opacity-50 scale-98' : 'opacity-100 scale-100'}`}>
          <CardHeader>
            <CardTitle>Recent Examples</CardTitle>
            <p className="text-sm text-muted-foreground">
              Latest analyzed articles
            </p>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {summary.recent_examples.slice(0, 3).map((item, i) => (
                <div 
                  key={i} 
                  className="space-y-1 transition-all duration-700 ease-out"
                  style={{
                    animationDelay: isFilterLoading ? '0ms' : `${i * 100}ms`,
                    animation: isFilterLoading ? 'none' : 'fadeInUp 0.8s ease-out forwards'
                  }}
                >
                  <h4 className="text-sm font-medium line-clamp-2">{item.title}</h4>
                  <div className="flex items-center gap-2">
                    <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600">
                      Example
                    </span>
                    <p className="text-xs text-muted-foreground">{item.source} • {item.published_at}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Articles - Trends-style animation */}
      {articles?.items && articles.items.length > 0 && articles.items.filter(item => item.articles).length > 0 && (
        <Card className={`transition-all duration-500 ${isFilterLoading ? 'opacity-50' : 'opacity-100'}`}>
          <CardHeader>
            <CardTitle>Recent Articles</CardTitle>
            <p className="text-sm text-muted-foreground">
              Latest articles with bias analysis
            </p>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {articles.items.filter(item => item.articles).slice(0, 10).map((item, i) => (
                <div 
                  key={i} 
                  className="flex items-start justify-between p-3 border rounded-lg transition-all duration-700 ease-out hover:shadow-sm"
                  style={{
                    animationDelay: isFilterLoading ? '0ms' : `${i * 100}ms`,
                    animation: isFilterLoading ? 'none' : 'fadeInUp 0.8s ease-out forwards'
                  }}
                >
                  <div className="flex-1">
                    <h4 className="font-medium line-clamp-2">{item.articles?.title || "No title"}</h4>
                    <p className="text-sm text-muted-foreground mt-1">
                      {item.articles?.source || "Unknown"} • {item.articles?.published_at ? new Date(item.articles.published_at).toLocaleDateString() : "Unknown date"}
                    </p>
                  </div>
                  <div className="ml-4 flex items-center gap-2">
                    <span 
                      className="text-xs px-2 py-1 rounded text-white"
                      style={{ backgroundColor: COLORS[item.model_metadata?.direction] || '#6b7280' }}
                    >
                      {item.model_metadata?.direction?.replace('_', '-') || 'unknown'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <style jsx>{`
        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  );
}
