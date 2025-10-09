import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { formatDate } from "@/lib/utils/date";
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

type BadgeVariant = 'default' | 'secondary' | 'destructive' | 'outline';

interface ArticleRowServerProps {
  articles: Article[];
  title: string;
  sourceValue: string;
}

export default async function ArticleRowServer({ articles, title, sourceValue }: ArticleRowServerProps) {
  const label = title ?? sourceValue;

  // Ensure articles is always an array to prevent hydration mismatches
  const safeArticles = articles || [];

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
      <div className="overflow-x-auto">
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
