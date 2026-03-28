import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type SourceOption = { value: string; label: string };

export function SearchHeader(props: {
  title: string;
  subtitle?: string;
  backHref?: string;
  action: string;
  queryName?: string;
  sourceName?: string;
  queryDefault?: string;
  sourceDefault?: string;
  sources?: ReadonlyArray<SourceOption>;
  rightMeta?: React.ReactNode;
}) {
  const {
    title,
    subtitle,
    backHref,
    action,
    queryName = "q",
    sourceName = "source",
    queryDefault = "",
    sourceDefault = "all",
    sources,
    rightMeta,
  } = props;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3 min-w-0">
          {backHref ? (
            <Button asChild variant="outline" size="icon" className="h-11 w-11 shrink-0" aria-label="Back" title="Back">
              <Link href={backHref}>
                <ChevronLeft className="h-4 w-4" />
              </Link>
            </Button>
          ) : null}
          <div className="space-y-1 min-w-0">
            <h1 className="u-serif text-3xl font-semibold tracking-tight break-words">{title}</h1>
            {subtitle ? <p className="text-sm text-muted-foreground break-words">{subtitle}</p> : null}
          </div>
        </div>

        {rightMeta ? <div className="flex items-center gap-2 sm:pt-1">{rightMeta}</div> : null}
      </div>

      <form className="flex flex-col md:flex-row items-stretch gap-2" action={action} method="get">
        {sources ? (
          <select
            name={sourceName}
            defaultValue={sourceDefault}
            className="h-11 border rounded-md px-3 text-sm md:w-56 bg-card"
          >
            {sources.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        ) : null}

        <Input
          type="text"
          name={queryName}
          defaultValue={queryDefault}
          placeholder="Search headlines or summaries..."
          className="h-11 bg-card"
        />
        <Button type="submit" variant="outline" className="h-11">
          Search
        </Button>
      </form>
    </div>
  );
}
