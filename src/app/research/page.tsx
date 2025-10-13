"use client";

import { useState, useEffect, useMemo } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { 
  TrendingUp, 
  TrendingDown, 
  Brain, 
  Network, 
  Target, 
  BarChart3, 
  Lightbulb,
  AlertTriangle,
  CheckCircle,
  Clock,
  Users,
  Globe
} from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell } from "recharts";

interface SentimentPrediction {
  predicted_sentiment: number;
  confidence_interval: [number, number];
  prediction_accuracy: number;
  trend_direction: string;
  next_week_forecast: Record<string, number>;
  key_factors: string[];
}

interface SourceBias {
  source: string;
  overall_sentiment_bias: number;
  political_bias_score: number;
  temporal_consistency: number;
  influence_score: number;
  editorial_positioning: string;
  articles_analyzed: number;
}

interface PropagationAnalysis {
  propagation_network: Record<string, unknown[]>;
  influence_scores: Record<string, number>;
  key_influencers: [string, number][];
  propagation_patterns: string[];
}

interface ResearchInsights {
  executive_summary: {
    total_articles_analyzed: number;
    analysis_period_days: number;
    average_sentiment_score: number;
    sentiment_distribution: Record<string, number>;
    key_trends: string[];
  };
  key_findings: string[];
  statistical_significance: {
    sample_size: number;
    confidence_level: number;
    margin_of_error: number;
    statistical_power: number;
  };
  methodological_contributions: string[];
  practical_implications: string[];
  future_research_directions: string[];
}

const PERIODS = [
  { value: "7d", label: "Last 7 Days" },
  { value: "30d", label: "Last 30 Days" },
  { value: "90d", label: "Last 90 Days" }
];

const COLORS = {
  positive: "#22c55e",
  negative: "#ef4444",
  neutral: "#6b7280",
  prediction: "#3b82f6",
  confidence: "#f59e0b"
};

export default function ResearchPage() {
  const [selectedPeriod, setSelectedPeriod] = useState("30d");
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("predictions");
  
  // Data states
  const [predictions, setPredictions] = useState<SentimentPrediction | null>(null);
  const [sourceBias, setSourceBias] = useState<SourceBias[]>([]);
  const [propagation, setPropagation] = useState<PropagationAnalysis | null>(null);
  const [insights, setInsights] = useState<ResearchInsights | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    
    // Clear previous data to ensure fresh display
    setPredictions(null);
    setSourceBias([]);
    setPropagation(null);
    setInsights(null);
    
    try {
      const baseUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      
      // Fetch all data in parallel with aggressive cache busting
      const cacheBust = Date.now() + Math.random() * 1000;
      const fetchOptions = {
        method: 'GET',
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0'
        }
      };
      
      const [predRes, biasRes, propRes, insightsRes] = await Promise.all([
        fetch(`${baseUrl}/research/sentiment-predictions?period=${selectedPeriod}&_t=${cacheBust}`, fetchOptions),
        fetch(`${baseUrl}/research/source-bias-analysis?period=${selectedPeriod}&_t=${cacheBust}`, fetchOptions),
        fetch(`${baseUrl}/research/sentiment-propagation?period=${selectedPeriod}&_t=${cacheBust}`, fetchOptions),
        fetch(`${baseUrl}/research/comprehensive-insights?period=${selectedPeriod}&_t=${cacheBust}`, fetchOptions)
      ]);

      if (predRes.ok) {
        const predData = await predRes.json();
        if (predData.ok) {
          setPredictions(predData.prediction);
        }
      }

      if (biasRes.ok) {
        const biasData = await biasRes.json();
        console.log('Bias data received:', biasData);
        console.log('Sources in bias data:', biasData.sources?.map((s: any) => s.source));
        if (biasData.ok) {
          setSourceBias(biasData.sources);
        }
      }

      if (propRes.ok) {
        const propData = await propRes.json();
        console.log('Propagation data received:', propData);
        if (propData.ok) {
          setPropagation(propData.propagation);
        }
      }

      if (insightsRes.ok) {
        const insightsData = await insightsRes.json();
        if (insightsData.ok) {
          setInsights(insightsData.insights);
        }
      }

    } catch (err) {
      setError("Failed to load research data. Please try again.");
      console.error("Research data fetch error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [selectedPeriod]);

  const getSentimentColor = (score: number) => {
    if (score > 0.1) return COLORS.positive;
    if (score < -0.1) return COLORS.negative;
    return COLORS.neutral;
  };

  const getBiasLabel = (bias: number) => {
    if (bias > 0.2) return "Optimistic";
    if (bias < -0.2) return "Pessimistic";
    return "Balanced";
  };

  const getInfluenceLevel = (score: number) => {
    if (score > 2) return "High";
    if (score > 1) return "Medium";
    return "Low";
  };

  // Normalize and deduplicate source names (e.g., Philstar vs PhilStar)
  const normalizeSourceLabel = (name: string): string => {
    const trimmed = (name || "").trim();
    const lower = trimmed.toLowerCase();
    const aliases: Record<string, string> = {
      "philstar": "Philstar",
      "phil star": "Philstar",
      "phil-star": "Philstar",
      "gma": "GMA",
      "manila times": "Manila Times",
      "manila bulletin": "Manila Bulletin",
      "sunstar": "Sunstar",
      "inquirer": "Inquirer",
      "rappler": "Rappler"
    };
    return aliases[lower] ?? trimmed.replace(/\b\w/g, (c) => c.toUpperCase());
  };

  // Build a cleaned, deduplicated bias array with aggregated metrics
  const cleanedBias = useMemo<SourceBias[]>(() => {
    const buckets: Record<string, {
      sumBias: number;
      sumPol: number;
      sumTemp: number;
      sumInfluence: number;
      totalArticles: number;
      sampleCount: number;
      editorial: string | null;
      exemplar?: SourceBias;
    }> = {};

    for (const s of sourceBias) {
      const label = normalizeSourceLabel(s.source);
      const existing = buckets[label] || {
        sumBias: 0,
        sumPol: 0,
        sumTemp: 0,
        sumInfluence: 0,
        totalArticles: 0,
        sampleCount: 0,
        editorial: s.editorial_positioning ?? "",
        exemplar: s
      };

      const weight = Math.max(1, s.articles_analyzed || 0);
      existing.sumBias += s.overall_sentiment_bias * weight;
      existing.sumPol += s.political_bias_score * weight;
      existing.sumTemp += s.temporal_consistency * weight;
      existing.sumInfluence += s.influence_score;
      existing.totalArticles += (s.articles_analyzed || 0);
      existing.sampleCount += weight;
      existing.editorial = s.editorial_positioning || existing.editorial;
      existing.exemplar = s;

      buckets[label] = existing;
    }

    return Object.entries(buckets).map(([label, b]) => ({
      source: label,
      overall_sentiment_bias: b.sumBias / Math.max(1, b.sampleCount),
      political_bias_score: b.sumPol / Math.max(1, b.sampleCount),
      temporal_consistency: b.sumTemp / Math.max(1, b.sampleCount),
      influence_score: b.sumInfluence / Math.max(1, b.sampleCount),
      editorial_positioning: b.editorial || (b.exemplar?.editorial_positioning ?? ""),
      articles_analyzed: b.totalArticles || (b.exemplar?.articles_analyzed ?? 0)
    }));
  }, [sourceBias]);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
          Advanced Sentiment Research Dashboard
        </h1>
        <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
          Revolutionary sentiment analysis for Philippine news media - 
          Predictive modeling, bias detection, and comprehensive insights
        </p>
        
        <div className="flex items-center justify-center gap-4">
          <Select value={selectedPeriod} onValueChange={setSelectedPeriod}>
            <SelectTrigger className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PERIODS.map((period) => (
                <SelectItem key={period.value} value={period.value}>
                  {period.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          
          <Button onClick={fetchData} disabled={loading}>
            {loading ? "Loading..." : "Refresh Data"}
          </Button>
          <Button 
            onClick={() => {
              // Force clear all state and fetch fresh data
              setPredictions(null);
              setSourceBias([]);
              setPropagation(null);
              setInsights(null);
              fetchData();
            }} 
            disabled={loading}
            variant="outline"
          >
            Force Refresh
          </Button>
        </div>
      </div>

      {error && (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Research Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="predictions" className="flex items-center gap-2">
            <Brain className="h-4 w-4" />
            Predictions
          </TabsTrigger>
          <TabsTrigger value="bias" className="flex items-center gap-2">
            <Target className="h-4 w-4" />
            Source Bias
          </TabsTrigger>
          <TabsTrigger value="propagation" className="flex items-center gap-2">
            <Network className="h-4 w-4" />
            Propagation
          </TabsTrigger>
          <TabsTrigger value="insights" className="flex items-center gap-2">
            <Lightbulb className="h-4 w-4" />
            Insights
          </TabsTrigger>
        </TabsList>

        {/* Sentiment Predictions Tab */}
        <TabsContent value="predictions" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Prediction Overview */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Brain className="h-5 w-5 text-blue-600" />
                  Sentiment Prediction
                </CardTitle>
                <CardDescription>
                  AI-powered forecast of future sentiment trends
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {predictions ? (
                  <>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Predicted Sentiment</span>
                      <div className="flex items-center gap-2">
                        <div 
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: getSentimentColor(predictions.predicted_sentiment) }}
                        />
                        <span className="font-bold">
                          {predictions.predicted_sentiment.toFixed(3)}
                        </span>
                      </div>
                    </div>
                    
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Confidence Interval</span>
                      <span className="text-sm">
                        [{predictions.confidence_interval[0].toFixed(3)}, {predictions.confidence_interval[1].toFixed(3)}]
                      </span>
                    </div>
                    
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Prediction Accuracy</span>
                      <span className="text-sm font-medium">
                        {(predictions.prediction_accuracy * 100).toFixed(1)}%
                      </span>
                    </div>
                    
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Trend Direction</span>
                      <Badge variant={predictions.trend_direction === "increasing" ? "default" : 
                                      predictions.trend_direction === "decreasing" ? "destructive" : "secondary"}>
                        {predictions.trend_direction}
                      </Badge>
                    </div>
                  </>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? "Loading predictions..." : "No prediction data available"}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Weekly Forecast */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Clock className="h-5 w-5 text-green-600" />
                  Next Week Forecast
                </CardTitle>
                <CardDescription>
                  Daily sentiment predictions for the next 7 days
                </CardDescription>
              </CardHeader>
              <CardContent>
                {predictions?.next_week_forecast ? (
                  <div className="space-y-2">
                    {Object.entries(predictions.next_week_forecast).map(([day, score]) => (
                      <div key={day} className="flex items-center justify-between">
                        <span className="text-sm">{day}</span>
                        <div className="flex items-center gap-2">
                          <div 
                            className="w-2 h-2 rounded-full"
                            style={{ backgroundColor: getSentimentColor(score) }}
                          />
                          <span className="text-sm font-medium">{score.toFixed(3)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    No forecast data available
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Key Factors */}
          {predictions?.key_factors && (
            <Card>
              <CardHeader>
                <CardTitle>Key Factors Influencing Sentiment</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {predictions.key_factors.map((factor, index) => (
                    <div key={index} className="flex items-start gap-2">
                      <CheckCircle className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
                      <span className="text-sm">{factor}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Source Bias Analysis Tab */}
        <TabsContent value="bias" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Bias Overview */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Target className="h-5 w-5 text-purple-600" />
                  Source Bias Analysis
                </CardTitle>
                <CardDescription>
                  Objective bias quantification across news sources
                </CardDescription>
              </CardHeader>
              <CardContent>
                {cleanedBias.length > 0 ? (
                  <div className="space-y-4">
                    {cleanedBias.slice(0, 5).map((source) => (
                      <div key={source.source} className="flex items-center justify-between p-3 border rounded-lg">
                        <div className="flex-1">
                          <div className="font-medium">{source.source}</div>
                          <div className="text-sm text-muted-foreground">
                            {source.articles_analyzed} articles analyzed
                          </div>
                        </div>
                        <div className="text-right space-y-1">
                          <div className="text-sm">
                            <span className="text-muted-foreground">Bias: </span>
                            <span className="font-medium">{getBiasLabel(source.overall_sentiment_bias)}</span>
                          </div>
                          <div className="text-sm">
                            <span className="text-muted-foreground">Influence: </span>
                            <Badge variant="outline">
                              {getInfluenceLevel(source.influence_score)}
                            </Badge>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    No bias analysis data available
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Bias Distribution Chart */}
            <Card>
              <CardHeader>
                <CardTitle>Bias Distribution</CardTitle>
                <CardDescription>
                  Sentiment bias scores across all sources
                </CardDescription>
              </CardHeader>
              <CardContent>
                {cleanedBias.length > 0 ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart 
                      key={`bias-chart-${selectedPeriod}-${cleanedBias.length}`}
                      data={cleanedBias.map(s => {
                        console.log('Chart data mapping:', s.source, s.overall_sentiment_bias);
                        return {
                          source: s.source,
                          bias: s.overall_sentiment_bias,
                          influence: s.influence_score
                        };
                      })}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis 
                        dataKey="source" 
                        angle={-45} 
                        textAnchor="end" 
                        height={80}
                        tick={{ fontSize: 12 }}
                      />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="bias" fill="#8884d8" />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    No chart data available
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Propagation Analysis Tab */}
        <TabsContent value="propagation" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Key Influencers */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5 text-orange-600" />
                  Key Influencers
                </CardTitle>
                <CardDescription>
                  News sources with highest influence on sentiment propagation
                </CardDescription>
              </CardHeader>
              <CardContent>
                {propagation?.key_influencers ? (
                  <div className="space-y-4">
                    {propagation.key_influencers.map(([source, score], index) => (
                      <div key={source} className="flex items-center justify-between p-3 border rounded-lg">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-gradient-to-r from-orange-400 to-red-500 flex items-center justify-center text-white font-bold">
                            {index + 1}
                          </div>
                          <div>
                            <div className="font-medium">{source}</div>
                            <div className="text-sm text-muted-foreground">
                              Influence Score: {score}
                            </div>
                          </div>
                        </div>
                        <Badge variant="outline">
                          {getInfluenceLevel(score)}
                        </Badge>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    No propagation data available
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Propagation Patterns */}
            <Card>
              <CardHeader>
                <CardTitle>Propagation Patterns</CardTitle>
                <CardDescription>
                  How sentiment spreads across news sources
                </CardDescription>
              </CardHeader>
              <CardContent>
                {propagation?.propagation_patterns ? (
                  <div className="space-y-3">
                    {propagation.propagation_patterns.map((pattern, index) => (
                      <div key={index} className="flex items-start gap-2">
                        <Network className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
                        <span className="text-sm">{pattern}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    No propagation patterns detected
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Research Insights Tab */}
        <TabsContent value="insights" className="space-y-6">
          {insights && (
            <>
              {/* Executive Summary */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="h-5 w-5 text-green-600" />
                    Executive Summary
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center p-4 border rounded-lg">
                      <div className="text-2xl font-bold text-blue-600">
                        {insights.executive_summary.total_articles_analyzed.toLocaleString()}
                      </div>
                      <div className="text-sm text-muted-foreground">Articles Analyzed</div>
                    </div>
                    <div className="text-center p-4 border rounded-lg">
                      <div className="text-2xl font-bold text-green-600">
                        {insights.executive_summary.analysis_period_days}
                      </div>
                      <div className="text-sm text-muted-foreground">Analysis Period (Days)</div>
                    </div>
                    <div className="text-center p-4 border rounded-lg">
                      <div className="text-2xl font-bold text-purple-600">
                        {insights.executive_summary.average_sentiment_score.toFixed(3)}
                      </div>
                      <div className="text-sm text-muted-foreground">Avg Sentiment Score</div>
                    </div>
                    <div className="text-center p-4 border rounded-lg">
                      <div className="text-2xl font-bold text-orange-600">
                        {(insights.statistical_significance.statistical_power * 100).toFixed(0)}%
                      </div>
                      <div className="text-sm text-muted-foreground">Statistical Power</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Key Findings */}
              <Card>
                <CardHeader>
                  <CardTitle>Key Research Findings</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {insights.key_findings.map((finding, index) => (
                      <div key={index} className="flex items-start gap-2">
                        <CheckCircle className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
                        <span className="text-sm">{finding}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Methodological Contributions */}
              <Card>
                <CardHeader>
                  <CardTitle>Methodological Contributions</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {insights.methodological_contributions.map((contribution, index) => (
                      <div key={index} className="flex items-start gap-2">
                        <Lightbulb className="h-4 w-4 text-yellow-600 mt-0.5 flex-shrink-0" />
                        <span className="text-sm">{contribution}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Practical Implications */}
              <Card>
                <CardHeader>
                  <CardTitle>Practical Implications</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {insights.practical_implications.map((implication, index) => (
                      <div key={index} className="flex items-start gap-2">
                        <Globe className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
                        <span className="text-sm">{implication}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
