export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "13.0.4"
  }
  public: {
    Tables: {
      article_duplicates: {
        Row: {
          article_id: number | null
          duplicate_of: number | null
          id: number
        }
        Insert: {
          article_id?: number | null
          duplicate_of?: number | null
          id?: number
        }
        Update: {
          article_id?: number | null
          duplicate_of?: number | null
          id?: number
        }
        Relationships: [
          {
            foreignKeyName: "article_duplicates_article_id_fkey"
            columns: ["article_id"]
            isOneToOne: false
            referencedRelation: "articles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "article_duplicates_duplicate_of_fkey"
            columns: ["duplicate_of"]
            isOneToOne: false
            referencedRelation: "articles"
            referencedColumns: ["id"]
          },
        ]
      }
      articles: {
        Row: {
          category: string | null
          content: string | null
          id: number
          inserted_at: string | null
          published_at: string | null
          raw_category: string | null
          source: string
          tags: string[] | null
          title: string
          updated_at: string | null
          url: string | null
        }
        Insert: {
          category?: string | null
          content?: string | null
          id?: number
          inserted_at?: string | null
          published_at?: string | null
          raw_category?: string | null
          source: string
          tags?: string[] | null
          title: string
          updated_at?: string | null
          url?: string | null
        }
        Update: {
          category?: string | null
          content?: string | null
          id?: number
          inserted_at?: string | null
          published_at?: string | null
          raw_category?: string | null
          source?: string
          tags?: string[] | null
          title?: string
          updated_at?: string | null
          url?: string | null
        }
        Relationships: []
      }
      bias_analysis: {
        Row: {
          article_id: number | null
          confidence_score: number | null
          created_at: string | null
          id: number
          model_metadata: Json | null
          model_type: string
          model_version: string
          political_bias_score: number | null
          processing_time_ms: number | null
          sentiment_label: string | null
          sentiment_score: number | null
          toxicity_score: number | null
        }
        Insert: {
          article_id?: number | null
          confidence_score?: number | null
          created_at?: string | null
          id?: number
          model_metadata?: Json | null
          model_type: string
          model_version: string
          political_bias_score?: number | null
          processing_time_ms?: number | null
          sentiment_label?: string | null
          sentiment_score?: number | null
          toxicity_score?: number | null
        }
        Update: {
          article_id?: number | null
          confidence_score?: number | null
          created_at?: string | null
          id?: number
          model_metadata?: Json | null
          model_type?: string
          model_version?: string
          political_bias_score?: number | null
          processing_time_ms?: number | null
          sentiment_label?: string | null
          sentiment_score?: number | null
          toxicity_score?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "bias_analysis_article_id_fkey"
            columns: ["article_id"]
            isOneToOne: false
            referencedRelation: "articles"
            referencedColumns: ["id"]
          },
        ]
      }
      pattern_predictions: {
        Row: {
          confidence_score: number | null
          created_at: string | null
          horizon: string
          id: number
          model_metadata: Json | null
          model_type: string
          model_version: string
          predicted_value: number | null
          scope_type: string
          scope_value: string
          valid_from: string | null
          valid_until: string | null
        }
        Insert: {
          confidence_score?: number | null
          created_at?: string | null
          horizon: string
          id?: number
          model_metadata?: Json | null
          model_type: string
          model_version: string
          predicted_value?: number | null
          scope_type: string
          scope_value: string
          valid_from?: string | null
          valid_until?: string | null
        }
        Update: {
          confidence_score?: number | null
          created_at?: string | null
          horizon?: string
          id?: number
          model_metadata?: Json | null
          model_type?: string
          model_version?: string
          predicted_value?: number | null
          scope_type?: string
          scope_value?: string
          valid_from?: string | null
          valid_until?: string | null
        }
        Relationships: []
      }
      raw_articles: {
        Row: {
          id: number
          raw_html: string | null
          scraped_at: string | null
          source: string
        }
        Insert: {
          id?: number
          raw_html?: string | null
          scraped_at?: string | null
          source: string
        }
        Update: {
          id?: number
          raw_html?: string | null
          scraped_at?: string | null
          source?: string
        }
        Relationships: []
      }
      scraping_logs: {
        Row: {
          articles_scraped: number
          completed_at: string | null
          error_message: string | null
          execution_time_ms: number | null
          id: number
          run_id: string
          source: string
          started_at: string
          status: Database["public"]["Enums"]["scrape_status"]
        }
        Insert: {
          articles_scraped?: number
          completed_at?: string | null
          error_message?: string | null
          execution_time_ms?: number | null
          id?: number
          run_id?: string
          source: string
          started_at?: string
          status: Database["public"]["Enums"]["scrape_status"]
        }
        Update: {
          articles_scraped?: number
          completed_at?: string | null
          error_message?: string | null
          execution_time_ms?: number | null
          id?: number
          run_id?: string
          source?: string
          started_at?: string
          status?: Database["public"]["Enums"]["scrape_status"]
        }
        Relationships: []
      }
    }
    Views: {
      bias_analysis_political_latest: {
        Row: {
          article_id: number | null
          confidence_score: number | null
          created_at: string | null
          id: number | null
          model_metadata: Json | null
          model_type: string | null
          model_version: string | null
          political_bias_score: number | null
          processing_time_ms: number | null
          sentiment_label: string | null
          sentiment_score: number | null
          toxicity_score: number | null
        }
        Relationships: [
          {
            foreignKeyName: "bias_analysis_article_id_fkey"
            columns: ["article_id"]
            isOneToOne: false
            referencedRelation: "articles"
            referencedColumns: ["id"]
          },
        ]
      }
      bias_analysis_sentiment_latest: {
        Row: {
          article_id: number | null
          confidence_score: number | null
          created_at: string | null
          id: number | null
          model_metadata: Json | null
          model_type: string | null
          model_version: string | null
          political_bias_score: number | null
          processing_time_ms: number | null
          sentiment_label: string | null
          sentiment_score: number | null
          toxicity_score: number | null
        }
        Relationships: [
          {
            foreignKeyName: "bias_analysis_article_id_fkey"
            columns: ["article_id"]
            isOneToOne: false
            referencedRelation: "articles"
            referencedColumns: ["id"]
          },
        ]
      }
      mv_sentiment_daily: {
        Row: {
          articles: number | null
          avg_sentiment: number | null
          day: string | null
          neg: number | null
          neu: number | null
          pos: number | null
          source: string | null
        }
        Relationships: []
      }
      v_article_counts_weekly: {
        Row: {
          category: string | null
          n: number | null
          source: string | null
          week: string | null
        }
        Relationships: []
      }
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      scrape_status: "success" | "error" | "partial"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      scrape_status: ["success", "error", "partial"],
    },
  },
} as const
