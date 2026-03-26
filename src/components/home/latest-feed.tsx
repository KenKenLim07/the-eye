import Link from "next/link";
import type { Article } from "@/lib/types";
import { formatDateTime, toMillis } from "@/lib/utils/date";
import LatestFeedClient from "@/components/home/latest-feed-client";

type Props = {
  articles: Article[];
  limit?: number;
};

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

export default function LatestFeed({ articles, limit = 15 }: Props) {
  const nowMs = Date.now();
  const items = (articles || [])
    .slice()
    .sort((a, b) => toMillis(b.published_at) - toMillis(a.published_at))
    .slice(0, limit);

  const enriched = items.map((a) => {
    const ageShort = formatAgeShort(a.published_at, nowMs);
    const absTime = a.published_at ? formatDateTime(a.published_at) : "Unknown";
    return { ...a, ageShort, absTime };
  });

  return (
    <div className="space-y-3">
      <div className="flex items-end justify-between gap-3">
        <div className="space-y-1">
          <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Just in</div>
          <h2 className="font-sans text-lg sm:text-2xl font-semibold tracking-tight">What’s happening now</h2>
        </div>
        <Link
          href={{ pathname: "/search", query: { sort: "newest" } }}
          className="text-sm border rounded-md px-3 py-2 bg-card hover:bg-accent/5 transition-colors min-h-[44px] inline-flex items-center"
        >
          Browse all
        </Link>
      </div>

      <LatestFeedClient items={enriched} />
    </div>
  );
}
