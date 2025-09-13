"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { 
  LineChart, 
  Line, 
  AreaChart, 
  Area, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from "recharts";
import { RefreshCw, TrendingUp, TrendingDown, Activity, Globe, Wifi, WifiOff } from "lucide-react";
import { useWebSocket } from "@/hooks/useWebSocket";

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
  { value: "GMA News Online", label: "GMA News Online" },
  { value: "Inquirer.net", label: "Inquirer.net" },
  { value: "Philstar.com", label: "Philstar.com" },
  { value: "Rappler", label: "Rappler" },
  { value: "Manila Bulletin", label: "Manila Bulletin" },
  { value: "Manila Times", label: "Manila Times" },
  { value: "Sunstar", label: "Sunstar" }
];

const PERIODS = [
  { value: "1d", label: "Last 24 Hours" },
  { value: "7d", label: "Last 7 Days" },
  { value: "30d", label: "Last 30 Days" }
];

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
  const [realTimeData, setRealTimeData] = useState<any>(null);

  // WebSocket connection for real-time updates
  const baseUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
  const wsUrl = baseUrl.replace('http', 'ws') + '/ws/trends';
  const { lastMessage, connectionStatus } = useWebSocket(wsUrl);

  // Update real-time data when WebSocket message arrives
  useEffect(() => {
    if (lastMessage?.type === 'trends_update') {
      setRealTimeData(lastMessage.data);
      setLastUpdated(new Date());
    }
  }, [lastMessage]);

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

  // Use real-time data if available, otherwise use fetched data
  const displaySummary = realTimeData ? {
    ...summary,
    total_articles: realTimeData.total_articles,
    positive_pct: realTimeData.positive_pct,
    negative_pct: realTimeData.negative_pct,
    neutral_pct: realTimeData.neutral_pct
  } : summary;

  // Prepare chart data
  const chartData = timeline.map(day => ({
    ...day,
    date: new Date(day.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }));

  const pieData = [
    { name: 'Positive', value: displaySummary.positive_pct, color: '#10b981' },
    { name: 'Negative', value: displaySummary.negative_pct, color: '#ef4444' },
    { name: 'Neutral', value: displaySummary.neutral_pct, color: '#6b7280' }
  ];

  const sentimentTrend = timeline.length > 1 ? 
    (timeline[timeline.length - 1].avg_sentiment - timeline[0].avg_sentiment) : 0;

  return (
    <div className="container mx-auto max-w-7xl p-4">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold">News Sentiment Analytics</h1>
            <p className="text-muted-foreground">
              Real-time sentiment analysis across Philippine news sources
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* Real-time connection status */}
            <div className="flex items-center gap-1">
              {connectionStatus === 'Open' ? (
                <Wifi className="h-4 w-4 text-green-600" />
              ) : (
                <WifiOff className="h-4 w-4 text-red-600" />
              )}
              <span className="text-xs text-muted-foreground">
                {connectionStatus === 'Open' ? 'Live' : 'Offline'}
              </span>
            </div>
            {lastUpdated && (
              <span className="text-sm text-muted-foreground">
                Last updated: {lastUpdated.toLocaleTimeString()}
              </span>
            )}
            <Button 
              onClick={loadData} 
              disabled={loading}
              variant="outline" 
              size="sm"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        {/* Filters */}
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="flex-1">
                <label className="text-sm font-medium mb-2 block">News Source</label>
                <Select value={selectedSource} onValueChange={setSelectedSource}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select source" />
                  </SelectTrigger>
                  <SelectContent>
                    {SOURCES.map(source => (
                      <SelectItem key={source.value} value={source.value}>
                        {source.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex-1">
                <label className="text-sm font-medium mb-2 block">Time Period</label>
                <Select value={selectedPeriod} onValueChange={setSelectedPeriod}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select period" />
                  </SelectTrigger>
                  <SelectContent>
                    {PERIODS.map(period => (
                      <SelectItem key={period.value} value={period.value}>
                        {period.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center">
                <Activity className="h-4 w-4 mr-2" />
                Total Articles
                {realTimeData && <Badge variant="secondary" className="ml-2 text-xs">Live</Badge>}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{displaySummary.total_articles.toLocaleString()}</div>
              <p className="text-xs text-muted-foreground">
                Last {displaySummary.period}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center">
                <TrendingUp className="h-4 w-4 mr-2 text-green-600" />
                Positive
                {realTimeData && <Badge variant="secondary" className="ml-2 text-xs">Live</Badge>}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">{displaySummary.positive_pct}%</div>
              <p className="text-xs text-muted-foreground">
                Positive sentiment
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center">
                <TrendingDown className="h-4 w-4 mr-2 text-red-600" />
                Negative
                {realTimeData && <Badge variant="secondary" className="ml-2 text-xs">Live</Badge>}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">{displaySummary.negative_pct}%</div>
              <p className="text-xs text-muted-foreground">
                Negative sentiment
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium flex items-center">
                <Globe className="h-4 w-4 mr-2" />
                Daily Average
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{displaySummary.avg_daily_articles}</div>
              <p className="text-xs text-muted-foreground">
                Articles per day
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Charts */}
        <Tabs defaultValue="timeline" className="space-y-4">
          <TabsList>
            <TabsTrigger value="timeline">Timeline</TabsTrigger>
            <TabsTrigger value="distribution">Distribution</TabsTrigger>
            <TabsTrigger value="volume">Volume</TabsTrigger>
          </TabsList>

          <TabsContent value="timeline">
            <Card>
              <CardHeader>
                <CardTitle>Sentiment Timeline</CardTitle>
                <CardDescription>
                  Sentiment distribution over time
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis />
                      <Tooltip 
                        formatter={(value, name) => [
                          `${value}%`, 
                          name === 'positive' ? 'Positive' : 
                          name === 'negative' ? 'Negative' : 'Neutral'
                        ]}
                      />
                      <Legend />
                      <Area 
                        type="monotone" 
                        dataKey="positive_pct" 
                        stackId="1" 
                        stroke="#10b981" 
                        fill="#10b981" 
                        fillOpacity={0.6}
                        name="positive"
                      />
                      <Area 
                        type="monotone" 
                        dataKey="neutral_pct" 
                        stackId="1" 
                        stroke="#6b7280" 
                        fill="#6b7280" 
                        fillOpacity={0.6}
                        name="neutral"
                      />
                      <Area 
                        type="monotone" 
                        dataKey="negative_pct" 
                        stackId="1" 
                        stroke="#ef4444" 
                        fill="#ef4444" 
                        fillOpacity={0.6}
                        name="negative"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="distribution">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle>Sentiment Distribution</CardTitle>
                  <CardDescription>
                    Overall sentiment breakdown
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={pieData}
                          cx="50%"
                          cy="50%"
                          innerRadius={60}
                          outerRadius={100}
                          paddingAngle={5}
                          dataKey="value"
                        >
                          {pieData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip formatter={(value) => `${value}%`} />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Daily Article Volume</CardTitle>
                  <CardDescription>
                    Number of articles published per day
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" />
                        <YAxis />
                        <Tooltip />
                        <Bar dataKey="total" fill="#3b82f6" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="volume">
            <Card>
              <CardHeader>
                <CardTitle>Sentiment Volume Trends</CardTitle>
                <CardDescription>
                  Absolute numbers of positive, negative, and neutral articles
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-80">
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
                        stroke="#10b981" 
                        strokeWidth={2}
                        name="Positive"
                      />
                      <Line 
                        type="monotone" 
                        dataKey="neutral" 
                        stroke="#6b7280" 
                        strokeWidth={2}
                        name="Neutral"
                      />
                      <Line 
                        type="monotone" 
                        dataKey="negative" 
                        stroke="#ef4444" 
                        strokeWidth={2}
                        name="Negative"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Detailed Timeline */}
        <Card>
          <CardHeader>
            <CardTitle>Daily Breakdown</CardTitle>
            <CardDescription>
              Detailed sentiment analysis for each day
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {timeline.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No data available for the selected period.
                </p>
              ) : (
                timeline.map((day) => (
                  <div key={day.date} className="border rounded-lg p-4 hover:bg-muted/50 transition-colors">
                    <div className="flex items-center justify-between mb-3">
                      <div className="font-medium">{new Date(day.date).toLocaleDateString('en-US', { 
                        weekday: 'long', 
                        year: 'numeric', 
                        month: 'long', 
                        day: 'numeric' 
                      })}</div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline">{day.total} articles</Badge>
                        <Badge variant={sentimentTrend > 0 ? "default" : sentimentTrend < 0 ? "destructive" : "secondary"}>
                          {day.avg_sentiment > 0 ? '+' : ''}{day.avg_sentiment.toFixed(2)} avg
                        </Badge>
                      </div>
                    </div>
                    
                    {/* Sentiment Bar */}
                    <div className="flex h-6 rounded overflow-hidden mb-3">
                      {day.positive > 0 && (
                        <div 
                          className="bg-green-500 flex items-center justify-center text-white text-xs font-medium" 
                          style={{ width: `${day.positive_pct}%` }}
                          title={`${day.positive} positive (${day.positive_pct}%)`}
                        >
                          {day.positive_pct > 10 ? `${day.positive_pct}%` : ''}
                        </div>
                      )}
                      {day.neutral > 0 && (
                        <div 
                          className="bg-gray-400 flex items-center justify-center text-white text-xs font-medium" 
                          style={{ width: `${day.neutral_pct}%` }}
                          title={`${day.neutral} neutral (${day.neutral_pct}%)`}
                        >
                          {day.neutral_pct > 10 ? `${day.neutral_pct}%` : ''}
                        </div>
                      )}
                      {day.negative > 0 && (
                        <div 
                          className="bg-red-500 flex items-center justify-center text-white text-xs font-medium" 
                          style={{ width: `${day.negative_pct}%` }}
                          title={`${day.negative} negative (${day.negative_pct}%)`}
                        >
                          {day.negative_pct > 10 ? `${day.negative_pct}%` : ''}
                        </div>
                      )}
                    </div>
                    
                    {/* Sentiment Stats */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div className="text-green-600">
                        <span className="font-medium">{day.positive}</span> positive ({day.positive_pct}%)
                      </div>
                      <div className="text-gray-600">
                        <span className="font-medium">{day.neutral}</span> neutral ({day.neutral_pct}%)
                      </div>
                      <div className="text-red-600">
                        <span className="font-medium">{day.negative}</span> negative ({day.negative_pct}%)
                      </div>
                      <div className="text-muted-foreground">
                        Avg: <span className="font-medium">{day.avg_sentiment.toFixed(2)}</span>
                      </div>
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
