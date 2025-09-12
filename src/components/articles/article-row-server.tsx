import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { formatDate } from "@/lib/utils/date";
import { Badge } from "@/components/ui/badge";
import { fetchLatestAnalysisByIds } from "@/lib/articles";

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

  const idList = (articles || []).map(a => Number(a.id)).filter(Boolean);
  const analysisById = await fetchLatestAnalysisByIds(idList);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold tracking-tight">{label}</h2>
        <Badge variant="secondary">{articles?.length || 0}</Badge>
      </div>
      <div className="overflow-x-auto">
        <div className="flex gap-4 pr-4">
          {(articles && articles.length > 0) ? (
            articles.map((a) => (
              <Card key={a.id} className="min-w-[280px] max-w-[320px]">
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
                      {(() => {
                        const row = analysisById[String(a.id)];
                        const label = row?.sentiment_label;
                        if (!label) return null;
                        const variant: BadgeVariant = label === 'positive' ? 'default' : label === 'negative' ? 'destructive' : 'secondary';
                        return <Badge variant={variant}>{label}</Badge>;
                      })()}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground line-clamp-3">{a.content || "No summary available."}</p>
                  {a.url && (
                    <a className="text-sm underline mt-3 inline-block" href={a.url} target="_blank" rel="noreferrer">
                      Read more →
                    </a>
                  )}
                </CardContent>
              </Card>
            ))
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
