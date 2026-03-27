import Link from "next/link";

export default function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="border-t bg-background/75 backdrop-blur supports-[backdrop-filter]:bg-background/55">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="py-10 space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
            <div className="md:col-span-5 space-y-3">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="u-serif text-xl font-semibold tracking-tight">PH‑Eye</div>
                  <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    Editorial analytics
                  </div>
                </div>
                <div className="hidden sm:flex items-center gap-2">
                </div>
              </div>

              <p className="text-sm text-muted-foreground leading-6 max-w-md">
                A Philippine news aggregator with lightweight sentiment + entity snapshots to support the Trends,
                Correlation, and Entities views.
              </p>
            </div>

            <div className="md:col-span-3 space-y-3">
              <h3 className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Explore</h3>
              <div className="grid gap-2 text-sm">
                <Link href="/" className="hover:underline underline-offset-4">
                  Home
                </Link>
                <Link href="/search" className="hover:underline underline-offset-4">
                  Search
                </Link>
                <Link href="/trends" className="hover:underline underline-offset-4">
                  Trends
                </Link>
                <Link href="/correlation" className="hover:underline underline-offset-4">
                  Correlation
                </Link>
                <Link href="/entities" className="hover:underline underline-offset-4">
                  Entities
                </Link>
              </div>
            </div>

            <div className="md:col-span-4 space-y-3">
              <h3 className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Sources</h3>
              <div className="flex flex-wrap gap-2">
                {[
                  "GMA",
                  "Rappler",
                  "Inquirer",
                  "Manila Times",
                  "Philstar",
                  "Sunstar",
                  "Manila Bulletin",
                ].map((source) => (
                  <Link
                    key={source}
                    href={`/source/${encodeURIComponent(source)}`}
                    className="inline-flex items-center rounded-full border bg-card px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent/5 hover:text-foreground transition-colors"
                  >
                    {source}
                  </Link>
                ))}
              </div>
              
            </div>
          </div>

          <div className="pt-6 border-t flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              © {year} PH‑Eye •
            </p>
            <p className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Built by Jose Marie Lim • Next.js + Supabase
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}
