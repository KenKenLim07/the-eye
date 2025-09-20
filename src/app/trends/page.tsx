"use client";

import { useState, useEffect, useTransition } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RefreshCw, Loader2, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { Skeleton } from "@/components/ui/skeleton";

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

// Loading skeleton components
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

  const loadData = async (showRefreshIndicator = false) => {
    if (showRefreshIndicator) {
      setIsRefreshing(true);
    } else {
      setLoading(true);
    }
    
    try {
      const trendsData = await fetchTrends(selectedSource !== "all" ? selectedSource : undefined, selectedPeriod);
      setData(trendsData);
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Failed to load trends:', error);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
      setIsFilterLoading(false);
    }
  };

  const handleSourceChange = (newSource: string) => {
    setIsFilterLoading(true);
    setSelectedSource(newSource);
  };

  const handlePeriodChange = (newPeriod: string) => {
    setIsFilterLoading(true);
    setSelectedPeriod(newPeriod);
  };

  const handleRefresh = () => {
    loadData(true);
  };

  useEffect(() => {
    loadData();
  }, [selectedSource, selectedPeriod]);

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const interval = setInterval(() => loadData(true), 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [selectedSource, selectedPeriod]);

  if (loading && !data) {
    return (
      <div className="container mx-auto max-w-6xl p-4">
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

  // Prepare data for charts
  const chartData = timeline.map(day => ({
    ...day,
    date: new Date(day.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }));

  const getSentimentIcon = (type: 'positive' | 'negative' | 'neutral') => {
    switch (type) {
      case 'positive': return <TrendingUp className="h-4 w-4" />;
      case 'negative': return <TrendingDown className="h-4 w-4" />;
      case 'neutral': return <Minus className="h-4 w-4" />;
    }
  };

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
              <Select 
                value={selectedSource} 
                onValueChange={handleSourceChange}
                disabled={isFilterLoading}
              >
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
              <Select 
                value={selectedPeriod} 
                onValueChange={handlePeriodChange}
                disabled={isFilterLoading}
              >
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
            <Button 
              onClick={handleRefresh} 
              variant="outline" 
              size="sm"
              disabled={isRefreshing || isFilterLoading}
            >
              {(isRefreshing || isFilterLoading) ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              Refresh
            </Button>
            {lastUpdated && (
              <span className="text-xs text-muted-foreground">
                Last updated: {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>

        {/* Summary Cards - Visual feedback during loading */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className={`transition-all duration-500 ${isFilterLoading ? 'opacity-50 scale-98' : 'opacity-100 scale-100'}`}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                Total Articles
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold transition-all duration-700 ease-out">{summary.total_articles}</div>
              <p className="text-xs text-muted-foreground">
                Last {summary.period}
              </p>
            </CardContent>
          </Card>

          <Card className={`transition-all duration-500 ${isFilterLoading ? 'opacity-50 scale-98' : 'opacity-100 scale-100'}`}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                {getSentimentIcon('positive')}
                Positive
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600 transition-all duration-700 ease-out">
                {summary.positive_pct}%
              </div>
              <p className="text-xs text-muted-foreground">Positive sentiment</p>
            </CardContent>
          </Card>

          <Card className={`transition-all duration-500 ${isFilterLoading ? 'opacity-50 scale-98' : 'opacity-100 scale-100'}`}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                {getSentimentIcon('negative')}
                Negative
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600 transition-all duration-700 ease-out">
                {summary.negative_pct}%
              </div>
              <p className="text-xs text-muted-foreground">Negative sentiment</p>
            </CardContent>
          </Card>

          <Card className={`transition-all duration-500 ${isFilterLoading ? 'opacity-50 scale-98' : 'opacity-100 scale-100'}`}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                Daily Average
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold transition-all duration-700 ease-out">{summary.avg_daily_articles}</div>
              <p className="text-xs text-muted-foreground">Articles per day</p>
            </CardContent>
          </Card>
        </div>

        {/* Sentiment Trends Chart - Visual feedback during loading */}
        <Card className={`transition-all duration-500 ${isFilterLoading ? 'opacity-50' : 'opacity-100'}`}>
          <CardHeader>
            <CardTitle>Sentiment Trends Over Time</CardTitle>
            <CardDescription>
              Daily sentiment distribution showing trends and patterns
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-96">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart 
                  data={chartData}
                  margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                >
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
                    animationDuration={isFilterLoading ? 0 : 1000}
                    animationEasing="ease-in-out"
                  />
                  <Line 
                    type="monotone" 
                    dataKey="negative" 
                    stroke={COLORS.negative} 
                    strokeWidth={3}
                    name="Negative"
                    dot={{ fill: COLORS.negative, strokeWidth: 2, r: 4 }}
                    animationDuration={isFilterLoading ? 0 : 1000}
                    animationEasing="ease-in-out"
                  />
                  <Line 
                    type="monotone" 
                    dataKey="neutral" 
                    stroke={COLORS.neutral} 
                    strokeWidth={3}
                    name="Neutral"
                    dot={{ fill: COLORS.neutral, strokeWidth: 2, r: 4 }}
                    animationDuration={isFilterLoading ? 0 : 1000}
                    animationEasing="ease-in-out"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Timeline - Visual feedback during loading */}
        <Card className={`transition-all duration-500 ${isFilterLoading ? 'opacity-50' : 'opacity-100'}`}>
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
                timeline.map((day, index) => (
                  <div 
                    key={day.date} 
                    className="border rounded-lg p-4 transition-all duration-500 hover:shadow-sm"
                    style={{
                      animationDelay: `${index * 100}ms`,
                      animation: isFilterLoading ? 'none' : 'fadeInUp 0.8s ease-out forwards'
                    }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="font-medium">{day.date}</div>
                      <Badge variant="outline">{day.total} articles</Badge>
                    </div>
                    
                    {/* Sentiment Bar */}
                    <div className="flex h-4 rounded overflow-hidden mb-2">
                      {day.positive > 0 && (
                        <div 
                          className="bg-green-500 transition-all duration-1000 ease-out" 
                          style={{ 
                            width: `${day.positive_pct}%`,
                            animationDelay: isFilterLoading ? '0ms' : `${index * 100 + 300}ms`
                          }}
                          title={`${day.positive} positive (${day.positive_pct}%)`}
                        />
                      )}
                      {day.neutral > 0 && (
                        <div 
                          className="bg-gray-400 transition-all duration-1000 ease-out" 
                          style={{ 
                            width: `${day.neutral_pct}%`,
                            animationDelay: isFilterLoading ? '0ms' : `${index * 100 + 400}ms`
                          }}
                          title={`${day.neutral} neutral (${day.neutral_pct}%)`}
                        />
                      )}
                      {day.negative > 0 && (
                        <div 
                          className="bg-red-500 transition-all duration-1000 ease-out" 
                          style={{ 
                            width: `${day.negative_pct}%`,
                            animationDelay: isFilterLoading ? '0ms' : `${index * 100 + 500}ms`
                          }}
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
