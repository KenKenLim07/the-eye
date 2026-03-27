"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import type { Article } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { CSSProperties } from "react";
import { ExternalLink, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import ArticleQuickViewDialog, { type QuickViewArticle } from "@/components/articles/article-quick-view-dialog";
import { useEffect, useRef, useState } from "react";

type LatestFeedItem = Article & {
  ageShort: string;
  absTime: string;
};

function sentimentBadge(sentiment: string | null | undefined): { label: string; title: string; className?: string } {
  const s = (sentiment || "").toLowerCase();
  if (s === "positive") return { label: "POS", title: "positive", className: "bg-emerald-600 text-white border-emerald-600 dark:bg-emerald-500" };
  if (s === "negative") return { label: "NEG", title: "negative", className: "bg-red-600 text-white border-red-600 dark:bg-red-500" };
  if (s === "neutral") return { label: "NEU", title: "neutral", className: "bg-slate-700 text-white border-slate-700 dark:bg-slate-500" };
  return { label: "UNL", title: "unlabeled", className: "bg-muted text-muted-foreground border-border" };
}

export default function LatestFeedClient(props: { items: LatestFeedItem[] }) {
  const items = props.items ?? [];
  const [active, setActive] = useState<QuickViewArticle | null>(null);
  const [open, setOpen] = useState(false);
  const closeTimerRef = useRef<number | null>(null);
  type CSSVarProperties = CSSProperties & Record<`--${string}`, string | number>;

  useEffect(() => {
    if (open) {
      if (closeTimerRef.current != null) window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
      return;
    }
    if (!active) return;
    if (closeTimerRef.current != null) window.clearTimeout(closeTimerRef.current);
    closeTimerRef.current = window.setTimeout(() => {
      setActive(null);
      closeTimerRef.current = null;
    }, 180);
    return () => {
      if (closeTimerRef.current != null) window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    };
  }, [active, open]);

  return (
    <div className="divide-y rounded-md border bg-card/60">
      {items.length === 0 ? (
        <div className="p-4 text-sm text-muted-foreground">No articles yet.</div>
      ) : (
        items.map((a, i) => {
          const s = sentimentBadge(a.sentiment);
          const style: CSSVarProperties = { "--i": i };
          return (
            <div
              key={`${a.source}-${a.id}`}
              className={cn(
                "px-3 py-2.5 sm:px-4 sm:py-3 hover:bg-accent/5 transition-colors",
                "u-stagger-item"
              )}
              style={style}
            >
              <div className="flex items-start justify-between gap-2 sm:gap-3">
                <div className="min-w-0 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      href={`/source/${encodeURIComponent(a.source)}`}
                      className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground hover:text-foreground underline-offset-4 hover:underline"
                    >
                      {a.source}
                    </Link>
                    {a.category ? (
                      <span className="hidden sm:inline u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                        {a.category}
                      </span>
                    ) : null}
                    <span className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground" title={a.absTime}>
                      {a.ageShort}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="u-mono text-[10px] tracking-widest text-muted-foreground/70" title={`Article ID ${a.id}`}>
                        #{a.id}
                      </span>
                      <Badge
                        className={cn(
                          "inline-flex items-center justify-center h-5 px-2 py-0 text-[10px] leading-none rounded-full border uppercase tracking-wide",
                          s.className
                        )}
                        title={`VADER sentiment: ${s.title}`}
                        aria-label={`Sentiment ${s.title}`}
                      >
                        {s.label}
                      </Badge>
                    </div>
                  </div>

                  {a.url ? (
                    <a
                      href={a.url}
                      target="_blank"
                      rel="noreferrer"
                      className="block u-serif text-[13px] sm:text-base font-semibold leading-snug tracking-tight hover:underline underline-offset-4 break-words line-clamp-3 sm:line-clamp-2"
                    >
                      {a.title}
                    </a>
                  ) : (
                    <div className="u-serif text-[13px] sm:text-base font-semibold leading-snug tracking-tight break-words line-clamp-3 sm:line-clamp-2">
                      {a.title}
                    </div>
                  )}
                </div>

                <div className="shrink-0 flex items-center gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="h-11 w-11 sm:hidden"
                    onClick={() => {
                      setActive(a);
                      setOpen(true);
                    }}
                    aria-label="Quick view"
                    title="Quick view"
                  >
                    <Eye className="h-3.5 w-3.5" />
                  </Button>

                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="hidden sm:inline-flex h-9 px-2.5 text-xs"
                    onClick={() => {
                      setActive(a);
                      setOpen(true);
                    }}
                  >
                    <Eye className="h-3.5 w-3.5" />
                    Quick view
                  </Button>

                  {a.url ? (
                    <a
                      href={a.url}
                      target="_blank"
                      rel="noreferrer"
                      className="shrink-0 text-sm underline hidden sm:inline-flex min-h-[44px] items-center"
                    >
                      Read original
                    </a>
                  ) : null}

                  {a.url ? (
                    <a
                      href={a.url}
                      target="_blank"
                      rel="noreferrer"
                      className="sm:hidden inline-flex items-center justify-center min-h-[44px] min-w-[44px] rounded-md border bg-card hover:bg-accent/5 transition-colors"
                      aria-label="Read original"
                      title="Read original"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  ) : null}
                </div>
              </div>
            </div>
          );
        })
      )}

      <ArticleQuickViewDialog
        article={active}
        open={open && !!active}
        onOpenChange={(open) => {
          setOpen(open);
        }}
      />
    </div>
  );
}
