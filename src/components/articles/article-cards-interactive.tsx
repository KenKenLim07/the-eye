"use client";

import { CSSProperties, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Eye, ExternalLink } from "lucide-react";
import { formatDate } from "@/lib/utils/date";

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
}

export function ArticleCardsInteractive({ articles }: ArticleCardsInteractiveProps) {
  const [openId, setOpenId] = useState<number | null>(null);
  const items = useMemo(() => articles ?? [], [articles]);
  type StaggerStyle = CSSProperties & { ["--i"]?: number };

  const sentimentClass = (s: string) => {
    if (s === "positive") return "bg-emerald-600 text-white border-transparent";
    if (s === "negative") return "bg-primary text-primary-foreground border-transparent";
    return "bg-muted text-foreground border-transparent";
  };

  return (
    <>
      {items.map((a, idx) => {
        const numericId = Number(a.id);
        const sentiment = a.sentiment;
        const staggerStyle: StaggerStyle = { ["--i"]: idx };

        return (
          <div key={a.id} className="group u-stagger-item" style={staggerStyle}>
            <Card className="transition-[transform,box-shadow,border-color] duration-200 hover:shadow-md hover:-translate-y-[1px] border-border/70">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="u-serif text-lg leading-tight line-clamp-2 group-hover:text-accent transition-colors flex-1">
                    {a.title}
                  </CardTitle>
                   
                  {/* VADER sentiment badge in top right */}
                  {sentiment && (
                    <Badge 
                      variant="outline"
                      className={`shrink-0 text-[10px] u-mono uppercase tracking-widest ${sentimentClass(sentiment)}`}
                    >
                      {sentiment}
                    </Badge>
                  )}
                </div>
                
                {/* Metadata badges below title */}
                <div className="flex items-center gap-2 flex-wrap text-xs text-muted-foreground">
                  <Badge variant="outline" className="u-mono uppercase tracking-widest text-[10px]">{a.source}</Badge>
                  {a.category && <Badge variant="secondary" className="u-mono uppercase tracking-widest text-[10px]">{a.category}</Badge>}
                  <Badge variant="outline" className="u-mono uppercase tracking-widest text-[10px]">{formatDate(a.published_at)}</Badge>
                  <span className="u-mono text-[10px] tracking-widest text-muted-foreground/70" title={`Article ID ${a.id}`}>
                    #{a.id}
                  </span>
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
                    onClick={() => setOpenId(numericId)}
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

            <Dialog open={openId === numericId} onOpenChange={(open) => setOpenId(open ? numericId : null)}>
              <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
                <DialogHeader className="flex-shrink-0">
                  <DialogTitle className="text-xl leading-tight pr-6">{a.title}</DialogTitle>
                  <DialogDescription className="text-sm text-muted-foreground">
                    Article details and metadata
                  </DialogDescription>
                </DialogHeader>
                
                {/* Badges moved outside DialogDescription to fix HTML validation */}
                <div className="flex items-center gap-2 flex-wrap mb-4">
                  <Badge variant="outline" className="u-mono uppercase tracking-widest text-[10px]">{a.source}</Badge>
                  {a.category && <Badge variant="secondary" className="u-mono uppercase tracking-widest text-[10px]">{a.category}</Badge>}
                  <Badge variant="outline" className="u-mono uppercase tracking-widest text-[10px]">{formatDate(a.published_at)}</Badge>
                  <span className="u-mono text-[10px] tracking-widest text-muted-foreground/70" title={`Article ID ${a.id}`}>
                    #{a.id}
                  </span>
                  {sentiment && (
                    <Badge variant="outline" className={`u-mono uppercase tracking-widest text-[10px] ${sentimentClass(sentiment)}`}>
                      {sentiment}
                    </Badge>
                  )}
                </div>

                {/* Scrollable content area */}
                <div className="flex-1 overflow-y-auto space-y-4 min-h-0">
                  <div className="prose prose-sm max-w-none">
                    <p className="text-sm leading-6 whitespace-pre-wrap text-foreground">
                      {a.content || "No summary available."}
                    </p>
                  </div>
                  
                  {a.url && (
                    <div className="pt-4 border-t">
                      <a 
                        className="inline-flex items-center text-sm text-accent hover:text-accent/80 underline" 
                        href={a.url} 
                        target="_blank" 
                        rel="noreferrer"
                      >
                        <ExternalLink className="h-4 w-4 mr-2" />
                        Read original article →
                      </a>
                    </div>
                  )}
                </div>
              </DialogContent>
            </Dialog>
          </div>
        );
      })}
    </>
  );
}
