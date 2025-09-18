import { useState, useEffect, useCallback, useRef } from 'react';

export interface BiasData {
  ok: boolean;
  articles: {
    total: number;
    by_source: Record<string, number>;
    by_date: Record<string, number>;
  };
  sentiment: {
    total_analyses: number;
    avg_compound: number;
    distribution: {
      positive: number;
      neutral: number;
      negative: number;
    };
  };
  political_bias: {
    total_analyses: number;
    avg_bias_score: number;
    avg_confidence: number;
    distribution: {
      pro_government: number;
      pro_opposition: number;
      neutral: number;
      mixed: number;
    };
  };
  source_comparison: Array<{
    source: string;
    article_count: number;
    political_bias: {
      avg_bias_score: number;
      avg_confidence: number;
      distribution: Record<string, number>;
    };
  }>;
  timeline: Array<{
    date: string;
    articles: number;
    political_bias: {
      avg_bias_score: number;
      avg_confidence: number;
      distribution: Record<string, number>;
    };
  }>;
  generated_at: string;
}

interface UseBiasDataReturn {
  data: BiasData | null;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  refetch: () => Promise<void>;
  isRefreshing: boolean;
}

export function useBiasData(period: string = '30d'): UseBiasDataReturn {
  const [data, setData] = useState<BiasData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const activeRequestIdRef = useRef(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  const fetchData = useCallback(async () => {
    const isInitialLoad = data === null;
    const requestId = ++activeRequestIdRef.current;

    // Cancel any in-flight request before starting a new one
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      if (isInitialLoad) {
        setLoading(true);
      } else {
        setIsRefreshing(true);
      }
      const response = await fetch(`http://localhost:8000/dashboard/comprehensive?period=${period}` , { signal: controller.signal });
      const result = await response.json();

      // Ignore if a newer request has started
      if (requestId !== activeRequestIdRef.current) return;
      
      if (result.ok) {
        setData(result);
        setLastUpdated(new Date());
        setError(null);
      } else {
        setError(result.error || 'Failed to fetch data');
      }
    } catch (err) {
      // Swallow abort errors; they are expected when switching fast
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }
      setError(err instanceof Error ? err.message : 'Network error');
    } finally {
      if (requestId !== activeRequestIdRef.current) return;
      if (isInitialLoad) {
        setLoading(false);
      } else {
        setIsRefreshing(false);
      }
    }
  }, [period, data]);

  useEffect(() => {
    fetchData();
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [fetchData]);

  return {
    data,
    loading,
    error,
    lastUpdated,
    refetch: fetchData,
    isRefreshing,
  };
}

// Auto-refresh hook
export function useBiasDataWithRefresh(period: string = '30d', intervalMs: number = 30000) {
  const biasData = useBiasData(period);

  useEffect(() => {
    if (!biasData.loading && !biasData.error) {
      const interval = setInterval(biasData.refetch, intervalMs);
      return () => clearInterval(interval);
    }
  }, [biasData.loading, biasData.error, biasData.refetch, intervalMs]);

  return biasData;
}
