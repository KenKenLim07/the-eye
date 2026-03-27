"use client";

import { useLayoutEffect, useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import AnimatedNumber from "@/components/ui/animated-number";
import SentimentSplitCard from "@/components/home/sentiment-split-card";
import { Clock, Layers, Newspaper, ShieldCheck } from "lucide-react";

type Sentiment = {
  label: string;
  sublabel?: string;
  positive: number;
  neutral: number;
  negative: number;
  unlabeled: number;
};

type Props = {
  totalArticles: number;
  articles24h: number;
  coveragePct: number | null;
  sentiment: Sentiment;
};

const SESSION_KEY = "ph-eye:kpi_countup_v1";

export default function HomeKpis({ totalArticles, articles24h, coveragePct, sentiment }: Props) {
  const [play, setPlay] = useState(false);

  useLayoutEffect(() => {
    try {
      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reduced) return;
      const nav = performance.getEntriesByType?.("navigation")?.[0] as PerformanceNavigationTiming | undefined;
      const navType = nav?.type;
      const isReload = navType === "reload";
      const isBackForward = navType === "back_forward";
      const already = sessionStorage.getItem(SESSION_KEY);

      // Animate on hard reloads, and on the first-ever home visit in this tab session.
      // Skip on client-side route switches (e.g., Entities -> Home) and back/forward restores.
      if (isBackForward) return;
      if (already && !isReload) return;

      sessionStorage.setItem(SESSION_KEY, "1");
      setPlay(true);
    } catch {
      // If storage is blocked, just skip the delight animation.
    }
  }, []);

  const sentimentTotal = useMemo(() => {
    return (
      Math.max(0, sentiment.positive) +
      Math.max(0, sentiment.neutral) +
      Math.max(0, sentiment.negative) +
      Math.max(0, sentiment.unlabeled)
    );
  }, [sentiment.negative, sentiment.neutral, sentiment.positive, sentiment.unlabeled]);

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 sm:gap-3">
      <Card>
        <CardContent className="p-2.5 sm:p-4">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-7 w-7 items-center justify-center rounded-md border bg-background/60" aria-hidden="true">
              <Newspaper className="h-3.5 w-3.5 text-muted-foreground" />
            </span>
            <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Database Total</div>
          </div>
          <div className="u-serif text-xl sm:text-3xl font-semibold tabular-nums">
            <AnimatedNumber value={totalArticles} animate={play} durationMs={900} className="u-serif" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-2.5 sm:p-4">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-7 w-7 items-center justify-center rounded-md border bg-background/60" aria-hidden="true">
              <Clock className="h-3.5 w-3.5 text-muted-foreground" />
            </span>
            <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">24h</div>
          </div>
          <div className="u-serif text-xl sm:text-3xl font-semibold tabular-nums">
            <AnimatedNumber value={articles24h} animate={play} durationMs={650} className="u-serif" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-2.5 sm:p-4">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-7 w-7 items-center justify-center rounded-md border bg-background/60" aria-hidden="true">
              <Layers className="h-3.5 w-3.5 text-muted-foreground" />
            </span>
            <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Sources</div>
          </div>
          <div className="u-serif text-xl sm:text-3xl font-semibold tabular-nums">7</div>
          <div className="hidden sm:block text-xs text-muted-foreground mt-1">
            GMA, Rappler, Inquirer, Manila Times, Philstar, Sunstar, Manila Bulletin
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-2.5 sm:p-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-md border bg-background/60" aria-hidden="true">
                <ShieldCheck className="h-3.5 w-3.5 text-muted-foreground" />
              </span>
              <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Coverage (7d)</div>
            </div>
            <span
              className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground"
              title="Percent of last-7d articles that have rows in article_sentiment_public (public VADER sentiment cache)."
              aria-label="Coverage info"
            >
              i
            </span>
          </div>
          <div className="u-serif text-xl sm:text-3xl font-semibold tabular-nums">
            {typeof coveragePct === "number" ? (
              <AnimatedNumber
                value={coveragePct}
                animate={play}
                durationMs={600}
                format={(n) => `${n}%`}
                className="u-serif"
              />
            ) : (
              "—"
            )}
          </div>
          <div className="mt-2 h-2 w-full rounded-full overflow-hidden border bg-muted" aria-label="Coverage progress bar">
            <div className="h-full bg-accent" style={{ width: `${coveragePct ?? 0}%` }} />
          </div>
          <div className="hidden sm:block text-xs text-muted-foreground mt-1">Articles with VADER sentiment rows</div>
        </CardContent>
      </Card>

      <div className="col-span-2 sm:col-span-1">
        <SentimentSplitCard
          label={sentiment.label}
          sublabel={sentiment.sublabel}
          positive={sentiment.positive}
          neutral={sentiment.neutral}
          negative={sentiment.negative}
          unlabeled={sentiment.unlabeled}
          totalSlot={<AnimatedNumber value={sentimentTotal} animate={play} durationMs={650} className="u-serif" />}
        />
      </div>
    </div>
  );
}
