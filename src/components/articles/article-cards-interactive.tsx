"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Eye, ExternalLink } from "lucide-react";
import { formatDate } from "@/lib/utils/date";

interface Article {
  id: number;
  title: string;
  content?: string;
  source: string;
  category?: string;
  published_at: string;
  url?: string;
  sentiment?: string; // Optional - may not be present
}

interface ArticleCardsInteractiveProps {
  articles: Article[];
}

export function ArticleCardsInteractive({ articles }: ArticleCardsInteractiveProps) {
  const [openId, setOpenId] = useState<number | null>(null);

  return (
    <>
      {articles.map((a) => {
        const numericId = Number(a.id);
        const sentiment = a.sentiment;

        return (
          <div key={a.id} className="group">
            <Card className="transition-all duration-200 hover:shadow-md">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-lg leading-tight line-clamp-2 group-hover:text-blue-600 transition-colors flex-1">
                    {a.title}
                  </CardTitle>
                  
                  {/* VADER sentiment badge in top right */}
                  {sentiment && (
                    <Badge 
                      variant={sentiment === "positive" ? "default" : sentiment === "negative" ? "destructive" : "secondary"}
                      className="shrink-0 text-xs"
                    >
                      {sentiment}
                    </Badge>
                  )}
                </div>
                
                {/* Metadata badges below title */}
                <div className="flex items-center gap-2 flex-wrap text-sm text-muted-foreground">
                  <Badge variant="outline">{a.source}</Badge>
                  {a.category && <Badge variant="secondary">{a.category}</Badge>}
                  <Badge variant="outline">{formatDate(a.published_at)}</Badge>
                </div>
              </CardHeader>
              
              <CardContent className="pt-0">
                <p className="text-sm text-muted-foreground line-clamp-3 leading-5">
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
                  <Badge variant="outline">{a.source}</Badge>
                  {a.category && <Badge variant="secondary">{a.category}</Badge>}
                  <Badge variant="outline">{formatDate(a.published_at)}</Badge>
                  {sentiment && (
                    <Badge variant={sentiment === "positive" ? "default" : sentiment === "negative" ? "destructive" : "secondary"}>
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
                        className="inline-flex items-center text-sm text-blue-600 hover:text-blue-800 underline" 
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
