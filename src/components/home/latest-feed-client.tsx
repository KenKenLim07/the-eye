"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import type { Article } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { CSSProperties } from "react";
import { ExternalLink, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import ArticleQuickViewDialog, { type QuickViewArticle } from "@/components/articles/article-quick-view-dialog";
import { useMemo, useState } from "react";

type LatestFeedItem = Article & {
  ageShort: string;
  absTime: string;
};

function sentimentBadge(sentiment: string | null | undefined): { label: string; className?: string } {
  const s = (sentiment || "").toLowerCase();
  if (s === "positive") return { label: "positive", className: "bg-emerald-600 text-white border-emerald-600 dark:bg-emerald-500" };
  if (s === "negative") return { label: "negative", className: "bg-red-600 text-white border-red-600 dark:bg-red-500" };
  if (s === "neutral") return { label: "neutral", className: "bg-slate-700 text-white border-slate-700 dark:bg-slate-500" };
  return { label: "unlabeled", className: "bg-muted text-muted-foreground border-border" };
}

export default function LatestFeedClient(props: { items: LatestFeedItem[] }) {
  const items = props.items || [];
  const [active, setActive] = useState<QuickViewArticle | null>(null);
  const activeOpen = !!active;
  type CSSVarProperties = CSSProperties & Record<`--${string}`, string | number>;

  const stableItems = useMemo(() => items, [items]);

  return (
    <div className="divide-y rounded-md border bg-card/60">
      {stableItems.length === 0 ? (
        <div className="p-4 text-sm text-muted-foreground">No articles yet.</div>
      ) : (
        stableItems.map((a, i) => {
          const s = sentimentBadge(a.sentiment);
          const style: CSSVarProperties = { "--i": i };
          return (
            <div
              key={`${a.source}-${a.id}`}
              className={cn(
                "px-3 py-3 sm:p-4 hover:bg-accent/5 transition-colors",
                "u-stagger-item"
              )}
              style={style}
            >
              <div className="flex items-start justify-between gap-2 sm:gap-3">
                <div className="min-w-0 space-y-2">
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
                    <span className="u-mono text-[10px] tracking-widest text-muted-foreground/70" title={`Article ID ${a.id}`}>
                      #{a.id}
                    </span>
                    <Badge className={cn("capitalize", s.className)}>{s.label}</Badge>
                  </div>

                  {a.url ? (
                    <a
                      href={a.url}
                      target="_blank"
                      rel="noreferrer"
                      className="block u-serif text-sm sm:text-lg font-semibold leading-snug tracking-tight hover:underline underline-offset-4 break-words"
                    >
                      {a.title}
                    </a>
                  ) : (
                    <div className="u-serif text-sm sm:text-lg font-semibold leading-snug tracking-tight break-words">
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
                    onClick={() => setActive(a)}
                    aria-label="Quick view"
                    title="Quick view"
                  >
                    <Eye className="h-4 w-4" />
                  </Button>

                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="hidden sm:inline-flex h-10"
                    onClick={() => setActive(a)}
                  >
                    <Eye className="h-4 w-4" />
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
                      <ExternalLink className="h-4 w-4" />
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
        open={activeOpen}
        onOpenChange={(open) => {
          if (!open) setActive(null);
        }}
      />
    </div>
  );
}
