import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import type { Article } from "@/lib/types";
import { formatDateTime } from "@/lib/utils/date";
import { cn } from "@/lib/utils";
import type { CSSProperties } from "react";

type Props = {
  articles: Article[];
  limit?: number;
};

type CSSVarProperties = CSSProperties & Record<`--${string}`, string | number>;

function toMillis(s: string | null): number {
  if (!s) return 0;
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? 0 : d.getTime();
}

function formatAgeShort(publishedAt: string | null, nowMs: number): string {
  const t = toMillis(publishedAt);
  if (!t) return "—";
  const diffSec = Math.max(0, Math.floor((nowMs - t) / 1000));
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay > 0) return `${diffDay}d`;
  if (diffHr > 0) return `${diffHr}h`;
  if (diffMin > 0) return `${diffMin}m`;
  return "now";
}

function sentimentBadge(sentiment: string | null | undefined): { label: string; className?: string } {
  const s = (sentiment || "").toLowerCase();
  if (s === "positive") return { label: "positive", className: "bg-emerald-600 text-white border-emerald-600 dark:bg-emerald-500" };
  if (s === "negative") return { label: "negative", className: "bg-red-600 text-white border-red-600 dark:bg-red-500" };
  if (s === "neutral") return { label: "neutral", className: "bg-slate-700 text-white border-slate-700 dark:bg-slate-500" };
  return { label: "unlabeled", className: "bg-muted text-muted-foreground border-border" };
}

export default function LatestFeed({ articles, limit = 24 }: Props) {
  const nowMs = Date.now();
  const items = (articles || [])
    .slice()
    .sort((a, b) => toMillis(b.published_at) - toMillis(a.published_at))
    .slice(0, limit);

  return (
    <div className="space-y-3">
      <div className="flex items-end justify-between gap-3">
        <div className="space-y-1">
          <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Unified feed</div>
          <h2 className="u-serif text-xl sm:text-2xl font-semibold tracking-tight">Latest</h2>
        </div>
        <Link
          href={{ pathname: "/search", query: { sort: "newest" } }}
          className="text-sm border rounded-md px-3 py-2 bg-card hover:bg-accent/5 transition-colors"
        >
          View more
        </Link>
      </div>

      <div className="divide-y rounded-md border bg-card/60">
        {items.length === 0 ? (
          <div className="p-4 text-sm text-muted-foreground">No articles yet.</div>
        ) : (
          items.map((a, i) => {
            const age = formatAgeShort(a.published_at, nowMs);
            const abs = a.published_at ? formatDateTime(a.published_at) : "Unknown";
            const s = sentimentBadge(a.sentiment);
            const style: CSSVarProperties = { "--i": i };
            return (
              <div
                key={`${a.source}-${a.id}`}
                className={cn(
                  "p-3 sm:p-4 hover:bg-accent/5 transition-colors",
                  "u-stagger-item"
                )}
                style={style}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={`/source/${encodeURIComponent(a.source)}`}
                        className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground hover:text-foreground underline-offset-4 hover:underline"
                      >
                        {a.source}
                      </Link>
                      {a.category ? (
                        <span className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                          {a.category}
                        </span>
                      ) : null}
                      <span className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground" title={abs}>
                        {age}
                      </span>
                      <Badge className={cn("capitalize", s.className)}>{s.label}</Badge>
                    </div>

                    {a.url ? (
                      <a
                        href={a.url}
                        target="_blank"
                        rel="noreferrer"
                        className="block u-serif text-base sm:text-lg font-semibold leading-snug tracking-tight hover:underline underline-offset-4 break-words"
                      >
                        {a.title}
                      </a>
                    ) : (
                      <div className="u-serif text-base sm:text-lg font-semibold leading-snug tracking-tight break-words">
                        {a.title}
                      </div>
                    )}
                  </div>

                  {a.url ? (
                    <a
                      href={a.url}
                      target="_blank"
                      rel="noreferrer"
                      className="shrink-0 text-sm underline"
                    >
                      Read original
                    </a>
                  ) : null}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
