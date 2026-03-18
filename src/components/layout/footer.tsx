import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t bg-background/75 backdrop-blur supports-[backdrop-filter]:bg-background/55">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="py-10 space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="space-y-2">
              <div className="u-serif text-lg font-semibold tracking-tight">PH-Eye</div>
              <p className="text-sm text-muted-foreground leading-6">
                Philippine news aggregation with lightweight sentiment and entity snapshots for analytics pages.
              </p>
            </div>

            <div className="space-y-3">
              <h3 className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Explore</h3>
              <div className="space-y-2">
                <Link href="/" className="block text-sm hover:underline">
                  Home
                </Link>
                <Link href="/search" className="block text-sm hover:underline">
                  Search
                </Link>
                <Link href="/entities" className="block text-sm hover:underline">
                  Entities
                </Link>
                <Link href="/trends" className="block text-sm hover:underline">
                  Trends
                </Link>
              </div>
            </div>

            <div className="space-y-3">
              <h3 className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Sources</h3>
              <div className="grid grid-cols-2 gap-2 text-sm text-muted-foreground">
                <span>GMA</span>
                <span>Rappler</span>
                <span>Inquirer</span>
                <span>Philstar</span>
                <span>Sunstar</span>
                <span>Manila Bulletin</span>
              </div>
            </div>
          </div>

          <div className="pt-6 border-t flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
            <p className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              (c) 2024 PH-Eye. Thesis demo build.
            </p>
            <p className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Built with Next.js + Supabase.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}

