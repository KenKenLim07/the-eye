"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { formatDateTime } from "@/lib/utils/date";
import { ExternalLink, X } from "lucide-react";

export type QuickViewArticle = {
  id: string | number;
  title: string;
  content: string | null;
  source: string;
  category: string | null;
  published_at: string | null;
  url: string | null;
  sentiment?: string | null;
};

function sentimentClass(sentiment: string | null | undefined): string {
  const v = (sentiment || "").toLowerCase();
  if (v === "positive") return "bg-emerald-600 text-white border-transparent dark:bg-emerald-500";
  if (v === "negative") return "bg-red-600 text-white border-transparent dark:bg-red-500";
  if (v === "neutral") return "bg-slate-700 text-white border-transparent dark:bg-slate-500";
  return "bg-muted text-muted-foreground border-border";
}

export default function ArticleQuickViewDialog(props: {
  article: QuickViewArticle | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { article, open, onOpenChange } = props;
  const content = (article?.content || "").trim();
  const looksLikeExcerpt = /\.\.\.$|…$/.test(content);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className={cn(
          "p-0 overflow-hidden !flex !flex-col",
          "w-full max-w-[calc(100%-1.25rem)] sm:max-w-3xl",
          "max-h-[92dvh]"
        )}
      >
        <div className="flex items-start gap-3 border-b bg-background/80 backdrop-blur px-3 sm:px-4 py-3">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-11 w-11 shrink-0"
            onClick={() => onOpenChange(false)}
            aria-label="Close quick view"
            title="Close"
          >
            <X className="h-4 w-4" />
          </Button>

          <div className="min-w-0 flex-1">
            <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Quick view</div>
            <div className="u-serif text-lg sm:text-2xl font-semibold leading-tight break-words">
              {article?.title ?? ""}
            </div>

            <div className="mt-2 flex items-center gap-2 flex-wrap">
              {article?.source ? (
                <Badge variant="outline" className="u-mono uppercase tracking-widest text-[10px]">
                  {article.source}
                </Badge>
              ) : null}
              {article?.category ? (
                <Badge variant="secondary" className="u-mono uppercase tracking-widest text-[10px]">
                  {article.category}
                </Badge>
              ) : null}
              {article?.published_at ? (
                <Badge variant="outline" className="u-mono uppercase tracking-widest text-[10px]">
                  {formatDateTime(article.published_at)}
                </Badge>
              ) : null}
              {article?.sentiment ? (
                <Badge
                  variant="outline"
                  className={cn("u-mono uppercase tracking-wide text-[10px]", sentimentClass(article.sentiment))}
                  title={`VADER sentiment: ${article.sentiment}`}
                >
                  {article.sentiment}
                </Badge>
              ) : (
                <Badge variant="outline" className="u-mono uppercase tracking-widest text-[10px] text-muted-foreground">
                  unlabeled
                </Badge>
              )}
              {article?.id != null ? (
                <span className="u-mono text-[10px] tracking-widest text-muted-foreground/70" title={`Article ID ${article.id}`}>
                  #{article.id}
                </span>
              ) : null}
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto overscroll-contain min-h-0 px-3 sm:px-4 py-4">
          <div className="prose prose-sm max-w-none">
            <p className="text-sm leading-7 whitespace-pre-wrap break-words text-foreground">
              {article?.content || "No summary available."}
            </p>
            {article?.url && looksLikeExcerpt ? (
              <div className="mt-4 rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                This summary looks truncated for this source. Use “Read original” for the full story.
              </div>
            ) : null}
          </div>
        </div>

        {article?.url ? (
          <div className="border-t px-3 sm:px-4 py-3 bg-background/80 backdrop-blur">
            <Button asChild className="h-11 w-full">
              <a href={article.url} target="_blank" rel="noreferrer">
                <ExternalLink className="h-4 w-4" />
                Read original
              </a>
            </Button>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
