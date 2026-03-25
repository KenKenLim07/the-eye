import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";
import { ArticleCardsInteractive } from "./article-cards-interactive";

interface Article {
  id: string | number;
  title: string;
  url: string | null;
  content: string | null;
  published_at: string | null;
  source: string;
  category: string | null;
}

interface ArticleRowServerProps {
  articles: Article[];
  title: string;
  sourceValue: string;
  collapsible?: boolean;
}

export default async function ArticleRowServer({ articles, title, sourceValue, collapsible = false }: ArticleRowServerProps) {
  const label = title ?? sourceValue;

  // Ensure articles is always an array to prevent hydration mismatches
  const safeArticles = articles || [];

  if (!collapsible) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold tracking-tight">{label}</h2>
        <div className="flex items-center gap-3">
          <Badge variant="secondary">{safeArticles.length}</Badge>
          <Link
            href={`/source/${encodeURIComponent(sourceValue)}`}
            className="text-sm underline"
          >
            View all
          </Link>
        </div>
      </div>
      <div className="overflow-x-auto -mx-2 px-2 sm:mx-0 sm:px-0">
        <div className="flex gap-4 pr-4">
          {safeArticles.length > 0 ? (
            <ArticleCardsInteractive articles={safeArticles} />
          ) : (
            <Card className="min-w-[280px] max-w-[320px]">
              <CardHeader>
                <CardTitle>No {label} articles</CardTitle>
                <CardDescription>Try running the scraper for {label}.</CardDescription>
              </CardHeader>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
  }

  return (
    <details open className="group rounded-md border bg-card/60">
      <summary className="cursor-pointer list-item px-3 py-3 sm:px-4 sm:py-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-md">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <h2 className="text-lg font-semibold tracking-tight truncate">{label}</h2>
            <Badge variant="secondary">{safeArticles.length}</Badge>
          </div>
          <Link
            href={`/source/${encodeURIComponent(sourceValue)}`}
            className="text-sm underline shrink-0"
          >
            View all
          </Link>
        </div>
      </summary>
      <div className="px-3 pb-3 sm:px-4 sm:pb-4">
        <div className="overflow-x-auto -mx-2 px-2 sm:mx-0 sm:px-0">
          <div className="flex gap-4 pr-4">
            {safeArticles.length > 0 ? (
              <ArticleCardsInteractive articles={safeArticles} />
            ) : (
              <Card className="min-w-[280px] max-w-[320px]">
                <CardHeader>
                  <CardTitle>No {label} articles</CardTitle>
                  <CardDescription>Try running the scraper for {label}.</CardDescription>
                </CardHeader>
              </Card>
            )}
          </div>
        </div>
      </div>
    </details>
  );
}
