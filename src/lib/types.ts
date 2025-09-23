export interface Article {
  id: number | string;
  title: string;
  url: string | null;
  content: string | null;
  published_at: string | null;
  source: string;
  category: string | null;
  // Optional fields that may be present in responses
  sentiment?: string | null;
}

export interface AnalysisRow {
  article_id: number;
  model_type: string; // e.g., 'sentiment' | 'political_bias'
  sentiment_label?: string | null;
  created_at: string; // ISO timestamp
} 