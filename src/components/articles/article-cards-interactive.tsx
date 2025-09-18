"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils/date";

interface Article {
  id: string | number;
  title: string;
  url: string | null;
  content: string | null;
  published_at: string | null;
  source: string;
  category: string | null;
}

interface AnalysisRowLike {
  sentiment_label?: string | null;
}

interface ArticleCardsInteractiveProps {
  articles: Article[];
  analysisById?: Record<number, AnalysisRowLike | null>;
}

export default function ArticleCardsInteractive({ articles, analysisById }: ArticleCardsInteractiveProps) {
  const [openId, setOpenId] = useState<number | null>(null);

  return (
    <>
      {articles.map((a) => {
        const numericId = Number(a.id);
        const analysis = analysisById ? analysisById[numericId] : undefined;
        const sentiment = analysis?.sentiment_label || null;
        return (
          <>
            <Card
              key={a.id}
              className="min-w-[280px] max-w-[320px] cursor-pointer"
              onClick={() => setOpenId(numericId)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setOpenId(numericId);
                }
              }}
            >
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <CardTitle className="line-clamp-2 text-base">{a.title}</CardTitle>
                    <CardDescription>
                      {a.source} • {a.category || "Uncategorized"}
                    </CardDescription>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <Badge variant="outline">{formatDate(a.published_at)}</Badge>
                    {sentiment && (
                      <Badge variant={sentiment === "positive" ? "default" : sentiment === "negative" ? "destructive" : "secondary"}>{sentiment}</Badge>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground line-clamp-3">{a.content || "No summary available."}</p>
                <div className="mt-3 flex items-center gap-3">
                  <button
                    className="text-sm underline"
                    onClick={(e) => {
                      e.stopPropagation();
                      setOpenId(numericId);
                    }}
                  >
                    Quick view →
                  </button>
                  {a.url && (
                    <a
                      className="text-sm underline"
                      href={a.url}
                      target="_blank"
                      rel="noreferrer"
                      onClick={(e) => e.stopPropagation()}
                    >
                      Open original ↗
                    </a>
                  )}
                </div>
              </CardContent>
            </Card>

            <Dialog open={openId === numericId} onOpenChange={(open) => setOpenId(open ? numericId : null)}>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>{a.title}</DialogTitle>
                  <DialogDescription>
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant="outline">{a.source}</Badge>
                      {a.category && <Badge variant="secondary">{a.category}</Badge>}
                      <Badge variant="outline">{formatDate(a.published_at)}</Badge>
                      {sentiment && (
                        <Badge variant={sentiment === "positive" ? "default" : sentiment === "negative" ? "destructive" : "secondary"}>{sentiment}</Badge>
                      )}
                    </div>
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <p className="text-sm leading-6 whitespace-pre-wrap">{a.content || "No summary available."}</p>
                  {a.url && (
                    <a className="text-sm underline" href={a.url} target="_blank" rel="noreferrer">
                      Read original article →
                    </a>
                  )}
                </div>
              </DialogContent>
            </Dialog>
          </>
        );
      })}
    </>
  );
} 