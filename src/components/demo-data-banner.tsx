"use client";

type DemoDataBannerProps = {
  computedAt?: string | null;
  /** Inclusive data window shown on the chart (e.g. from snapshot timeline). */
  dataFrom?: string | null;
  dataTo?: string | null;
  className?: string;
};

function formatWhen(iso?: string | null): string | null {
  if (!iso) return null;
  // Accept full ISO or YYYY-MM-DD
  const d = new Date(iso.length <= 10 ? `${iso}T12:00:00Z` : iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * Shown on Trends / Correlation / Entities when the site is in portfolio
 * snapshot mode (frozen analytics; scrapers not running).
 */
export function DemoDataBanner({
  computedAt,
  dataFrom,
  dataTo,
  className,
}: DemoDataBannerProps) {
  const frozenOn = formatWhen(computedAt);
  const from = formatWhen(dataFrom);
  const to = formatWhen(dataTo);
  const range =
    from && to ? (from === to ? from : `${from} – ${to}`) : from || to || null;

  return (
    <div
      className={
        className ??
        "rounded-md border border-amber-600/25 bg-amber-500/10 px-3 py-2 text-sm text-amber-950 dark:border-amber-500/30 dark:text-amber-100"
      }
      role="status"
    >
      <span className="font-medium">Portfolio demo data.</span>{" "}
      Charts are served from a frozen Supabase snapshot
      {range ? (
        <>
          {" "}
          covering <span className="font-medium">{range}</span>
        </>
      ) : null}
      {frozenOn ? <> (frozen {frozenOn})</> : null}
      — live scraping is not running.
    </div>
  );
}
