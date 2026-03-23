import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { formatDateTime } from "@/lib/utils/date";
import { cn } from "@/lib/utils";

type Props = {
  sources: string[];
  lastUpdated: string | null;
};

export default function HomeControlBar({ sources, lastUpdated }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex flex-col md:flex-row md:items-center gap-2">
        <form action="/search" method="get" className="flex flex-1 items-center gap-2">
          <Input
            name="q"
            placeholder="Search headlines or summaries…"
            className="h-10 bg-card"
            aria-label="Search"
          />
          <Button type="submit" className="h-10">
            Search
          </Button>
        </form>

        <div className="flex items-center justify-between md:justify-end gap-3">
          <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
            {lastUpdated ? `As of ${formatDateTime(lastUpdated)}` : ""}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {sources.map((s) => (
          <Link
            key={s}
            href={`/source/${encodeURIComponent(s)}`}
            className={cn(
              "inline-flex items-center gap-2 rounded-md border px-3 py-2 text-xs",
              "bg-card hover:bg-accent/5 transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            )}
          >
            <span className="u-mono text-[10px] uppercase tracking-widest">{s}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}

