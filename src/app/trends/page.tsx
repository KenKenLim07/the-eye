"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RefreshCw } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

interface TrendsData {
  ok: boolean;
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
  { value: "1d", label: "Last 24 Hours" },
  { value: "7d", label: "Last 7 Days" },
  { value: "30d", label: "Last 30 Days" }
];

const COLORS = {
  positive: "#22c55e",
  negative: "#ef4444", 
  neutral: "#6b7280"
};

async function fetchTrends(source?: string, period: string = "7d"): Promise<TrendsData> {
  const base = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
  const params = new URLSearchParams({ period });
  if (source && source !== "all") params.set('source', source);
  
  try {
    const res = await fetch(`${base}/ml/trends?${params}`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (error) {
    console.error('Failed to fetch trends:', error);
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

export default function TrendsPage() {
  const [data, setData] = useState<TrendsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedSource, setSelectedSource] = useState("all");
  const [selectedPeriod, setSelectedPeriod] = useState("7d");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const trendsData = await fetchTrends(selectedSource !== "all" ? selectedSource : undefined, selectedPeriod);
      setData(trendsData);
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Failed to load trends:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedSource, selectedPeriod]);

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const interval = setInterval(loadData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [selectedSource, selectedPeriod]);

  if (loading && !data) {
    return (
      <div className="container mx-auto max-w-6xl p-4">
        <div className="flex items-center justify-center h-64">
          <div className="flex items-center space-x-2">
            <RefreshCw className="h-4 w-4 animate-spin" />
            <span>Loading trends data...</span>
          </div>
        </div>
      </div>
    );
  }

  if (!data?.ok) {
    return (
      <div className="container mx-auto max-w-6xl p-4">
        <h1 className="text-3xl font-bold mb-6">News Sentiment Trends</h1>
        <Card>
          <CardContent className="p-6">
            <p className="text-muted-foreground">Failed to load trends data. Please try again later.</p>
            <Button onClick={loadData} className="mt-4">
              <RefreshCw className="h-4 w-4 mr-2" />
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const { summary, timeline } = data;

  // Prepare data for charts
  const chartData = timeline.map(day => ({
    ...day,
    date: new Date(day.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }));



  return (
    <div className="container mx-auto max-w-6xl p-4">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">News Sentiment Trends</h1>
          <p className="text-muted-foreground">
            Analyzing sentiment patterns across Philippine news sources
          </p>
        </div>

        {/* Filter Controls */}
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
          <div className="flex gap-4">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Source</label>
              <Select value={selectedSource} onValueChange={setSelectedSource}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Select source" />
                </SelectTrigger>
                <SelectContent>
                  {SOURCES.map((source) => (
                    <SelectItem key={source.value} value={source.value}>
                      {source.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium">Period</label>
              <Select value={selectedPeriod} onValueChange={setSelectedPeriod}>
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
          
          <div className="flex items-center gap-2">
            <Button onClick={loadData} variant="outline" size="sm">
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
            {lastUpdated && (
              <span className="text-xs text-muted-foreground">
                Last updated: {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Total Articles</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{summary.total_articles}</div>
              <p className="text-xs text-muted-foreground">
                Last {summary.period}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Positive</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">
                {summary.positive_pct}%
              </div>
              <p className="text-xs text-muted-foreground">Positive sentiment</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Negative</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">
                {summary.negative_pct}%
              </div>
              <p className="text-xs text-muted-foreground">Negative sentiment</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Daily Average</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{summary.avg_daily_articles}</div>
              <p className="text-xs text-muted-foreground">Articles per day</p>
            </CardContent>
          </Card>
        </div>

        {/* Sentiment Trends Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Sentiment Trends Over Time</CardTitle>
            <CardDescription>
              Daily sentiment distribution showing trends and patterns
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-96">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line 
                    type="monotone" 
                    dataKey="positive" 
                    stroke={COLORS.positive} 
                    strokeWidth={3}
                    name="Positive"
                    dot={{ fill: COLORS.positive, strokeWidth: 2, r: 4 }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="negative" 
                    stroke={COLORS.negative} 
                    strokeWidth={3}
                    name="Negative"
                    dot={{ fill: COLORS.negative, strokeWidth: 2, r: 4 }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="neutral" 
                    stroke={COLORS.neutral} 
                    strokeWidth={3}
                    name="Neutral"
                    dot={{ fill: COLORS.neutral, strokeWidth: 2, r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Timeline */}
        <Card>
          <CardHeader>
            <CardTitle>Daily Sentiment Timeline</CardTitle>
            <CardDescription>
              Sentiment distribution over the last {summary.period}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {timeline.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No data available for the selected period and source.
                </p>
              ) : (
                timeline.map((day) => (
                  <div key={day.date} className="border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="font-medium">{day.date}</div>
                      <Badge variant="outline">{day.total} articles</Badge>
                    </div>
                    
                    {/* Sentiment Bar */}
                    <div className="flex h-4 rounded overflow-hidden mb-2">
                      {day.positive > 0 && (
                        <div 
                          className="bg-green-500" 
                          style={{ width: `${day.positive_pct}%` }}
                          title={`${day.positive} positive (${day.positive_pct}%)`}
                        />
                      )}
                      {day.neutral > 0 && (
                        <div 
                          className="bg-gray-400" 
                          style={{ width: `${day.neutral_pct}%` }}
                          title={`${day.neutral} neutral (${day.neutral_pct}%)`}
                        />
                      )}
                      {day.negative > 0 && (
                        <div 
                          className="bg-red-500" 
                          style={{ width: `${day.negative_pct}%` }}
                          title={`${day.negative} negative (${day.negative_pct}%)`}
                        />
                      )}
                    </div>
                    
                    {/* Sentiment Stats */}
                    <div className="flex gap-4 text-sm text-muted-foreground">
                      <span className="text-green-600">
                        Positive: {day.positive} ({day.positive_pct}%)
                      </span>
                      <span className="text-gray-600">
                        Neutral: {day.neutral} ({day.neutral_pct}%)
                      </span>
                      <span className="text-red-600">
                        Negative: {day.negative} ({day.negative_pct}%)
                      </span>
                      <span>
                        Avg Score: {day.avg_sentiment}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
