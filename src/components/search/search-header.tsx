import Link from "next/link";

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
  sources?: SourceOption[];
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
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="u-serif text-3xl font-semibold tracking-tight">{title}</h1>
          {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
        </div>
        <div className="flex items-center gap-3">
          {rightMeta}
          {backHref ? (
            <Link href={backHref} className="u-mono text-[10px] uppercase tracking-widest underline text-muted-foreground">
              Back
            </Link>
          ) : null}
        </div>
      </div>

      <form className="flex flex-col md:flex-row items-stretch gap-2" action={action} method="get">
        {sources ? (
          <select
            name={sourceName}
            defaultValue={sourceDefault}
            className="border rounded-md px-3 py-2 text-sm md:w-56 bg-card"
          >
            {sources.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        ) : null}

        <input
          type="text"
          name={queryName}
          defaultValue={queryDefault}
          placeholder="Search headlines or summaries..."
          className="flex-1 border rounded-md px-3 py-2 text-sm bg-card"
        />
        <button className="text-sm border rounded-md px-4 py-2 bg-card hover:bg-accent/5 transition-colors">
          Search
        </button>
      </form>
    </div>
  );
}

