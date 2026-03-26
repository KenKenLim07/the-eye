"use client";

import { CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Eye, ExternalLink } from "lucide-react";
import { formatDate } from "@/lib/utils/date";
import ArticleQuickViewDialog, { type QuickViewArticle } from "./article-quick-view-dialog";

interface Article {
  id: number | string;
  title: string;
  content: string | null;
  source: string;
  category: string | null;
  published_at: string | null;
  url: string | null;
  sentiment?: string | null; // Optional - may not be present
}

interface ArticleCardsInteractiveProps {
  articles: Article[];
  layout?: "carousel" | "grid";
}

export function ArticleCardsInteractive({ articles, layout = "carousel" }: ArticleCardsInteractiveProps) {
  const [active, setActive] = useState<QuickViewArticle | null>(null);
  const [open, setOpen] = useState(false);
  const closeTimerRef = useRef<number | null>(null);
  const items = useMemo(() => articles ?? [], [articles]);
  type StaggerStyle = CSSProperties & { ["--i"]?: number };

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

  const sentimentLabelShort = (s: string) => {
    const v = (s || "").toLowerCase();
    if (v === "positive") return "POS";
    if (v === "negative") return "NEG";
    if (v === "neutral") return "NEU";
    return "UNK";
  };

  const sentimentClass = (s: string | null | undefined) => {
    const v = (s || "").toLowerCase();
    if (v === "positive") return "bg-emerald-600 text-white border-transparent";
    if (v === "negative") return "bg-red-600 text-white border-transparent dark:bg-red-500";
    if (v === "neutral") return "bg-slate-700 text-white border-transparent dark:bg-slate-500";
    return "bg-muted text-muted-foreground border-border";
  };

  return (
    <>
      {items.map((a, idx) => {
        const sentiment = a.sentiment;
        const sentimentFullLabel = sentiment || "unlabeled";
        const staggerStyle: StaggerStyle = { ["--i"]: idx };

        return (
          <div
            key={a.id}
            className={[
              "group u-stagger-item min-w-0",
              layout === "grid" ? "w-full" : "flex-none w-[280px] sm:w-[320px] lg:w-[360px]",
            ].join(" ")}
            style={staggerStyle}
          >
            <Card className="h-full transition-[transform,box-shadow,border-color] duration-200 hover:shadow-md hover:-translate-y-[1px] border-border/70">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2 min-w-0">
                  <div className="min-w-0 flex-1 space-y-2">
                    {/* Metadata badges */}
                    <div className="flex items-center gap-2 flex-wrap text-xs text-muted-foreground">
                      <Badge variant="outline" className="u-mono uppercase tracking-widest text-[10px]">
                        {a.source}
                      </Badge>
                      {a.category && (
                        <Badge variant="secondary" className="u-mono uppercase tracking-widest text-[10px]">
                          {a.category}
                        </Badge>
                      )}
                      <Badge variant="outline" className="u-mono uppercase tracking-widest text-[10px]">
                        {formatDate(a.published_at)}
                      </Badge>
                      <span className="u-mono text-[10px] tracking-widest text-muted-foreground/70" title={`Article ID ${a.id}`}>
                        #{a.id}
                      </span>
                    </div>

                    <CardTitle
                      className={[
                        "u-serif text-[15px] sm:text-lg leading-tight",
                        "line-clamp-3 sm:line-clamp-2",
                        "break-words hyphens-auto",
                        "group-hover:text-accent transition-colors",
                      ].join(" ")}
                      title={a.title}
                    >
                      {a.title}
                    </CardTitle>
                  </div>

                  {/* VADER sentiment badge */}
                  <Badge
                    variant="outline"
                    className={[
                      "shrink-0 text-[10px] u-mono uppercase",
                      "tracking-wide px-2 py-0.5",
                      sentimentClass(sentiment),
                    ].join(" ")}
                    title={`VADER sentiment: ${sentimentFullLabel}`}
                    aria-label={`VADER sentiment ${sentimentFullLabel}`}
                  >
                    {sentimentLabelShort(sentimentFullLabel)}
                  </Badge>
                </div>
              </CardHeader>
               
              <CardContent className="pt-0">
                <div className="h-px bg-border/60 mb-3" />
                <p className="text-sm text-muted-foreground line-clamp-3 leading-6">
                  {a.content || "No summary available."}
                </p>
                <div className="flex items-center justify-between mt-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setActive(a);
                      setOpen(true);
                    }}
                    className="text-xs"
                  >
                    <Eye className="h-3 w-3 mr-1" />
                    Quick view
                  </Button>
                  {a.url && (
                    <Button variant="ghost" size="sm" asChild className="text-xs">
                      <a href={a.url} target="_blank" rel="noreferrer">
                        <ExternalLink className="h-3 w-3 mr-1" />
                        Read original
                      </a>
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        );
      })}

      <ArticleQuickViewDialog
        article={active}
        open={open && !!active}
        onOpenChange={(open) => {
          setOpen(open);
        }}
      />
    </>
  );
}
