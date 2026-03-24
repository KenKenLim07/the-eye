"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Menu, Moon, Search, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetClose, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { formatDateTime } from "@/lib/utils/date";

export default function Navigation() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [isDark, setIsDark] = useState(false);

  const navItems = useMemo(
    () => [
      { href: "/", label: "Home" },
      { href: "/search", label: "Search" },
      { href: "/trends", label: "Trends" },
      { href: "/correlation", label: "Correlation" },
      { href: "/entities", label: "Entities" },
    ],
    []
  );

  useEffect(() => {
    // Close the sheet on route changes (safety net for non-link navigations).
    setMobileOpen(false);
  }, [pathname]);

  useEffect(() => {
    let cancelled = false;
    // Lightweight “as of” indicator for demo polish (Supabase-backed API route).
    fetch("/api/articles?pageSize=1", { cache: "no-store" })
      .then((r) => r.json())
      .then((json) => {
        if (cancelled) return;
        const ts = json?.data?.[0]?.published_at as string | null | undefined;
        if (!ts) return;
        setLastUpdated(ts);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    // Keep button state in sync with the html class toggled by the inline <head> script.
    setIsDark(document.documentElement.classList.contains("dark"));
  }, []);

  const toggleTheme = () => {
    const next = !document.documentElement.classList.contains("dark");
    document.documentElement.classList.toggle("dark", next);
    document.documentElement.style.colorScheme = next ? "dark" : "light";
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {}
    setIsDark(next);
  };

  return (
    <nav className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between gap-3">
          <Link href="/" className="flex items-center gap-3">
            <div className="leading-none">
              <div className="u-serif text-xl font-semibold tracking-tight">PH‑Eye</div>
              <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                Editorial analytics
              </div>
            </div>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-6">
            {navItems.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={[
                    "group relative px-1 py-2 text-sm font-medium transition-colors",
                    active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                  ].join(" ")}
                >
                  <span className="u-mono text-[12px] tracking-wide">{item.label}</span>
                  <span
                    aria-hidden="true"
                    className={[
                      "pointer-events-none absolute -bottom-px left-0 h-0.5 w-full rounded-full transition-opacity",
                      active ? "bg-primary opacity-100" : "bg-border opacity-0 group-hover:opacity-100",
                    ].join(" ")}
                  />
                </Link>
              );
            })}
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            {lastUpdated && (
              <div className="hidden lg:block u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                As of {formatDateTime(lastUpdated)}
              </div>
            )}

            <Button asChild variant="outline" size="icon" className="hidden md:inline-flex">
              <Link href="/search" aria-label="Search" title="Search">
                <Search className="h-4 w-4" />
              </Link>
            </Button>

            <Button
              type="button"
              onClick={toggleTheme}
              variant="outline"
              size="icon"
              aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
              title={isDark ? "Light mode" : "Dark mode"}
            >
              {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>

            {/* Mobile menu */}
            <div className="md:hidden">
              <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
                <SheetTrigger asChild>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="h-11 w-11 hover:bg-muted hover:text-foreground"
                    aria-label="Open menu"
                  >
                    <Menu className="h-5 w-5" />
                  </Button>
                </SheetTrigger>

                <SheetContent
                  side="bottom"
                  className="p-4 sm:p-5 rounded-t-xl border-t max-h-[85dvh] overflow-y-auto pb-[max(1rem,env(safe-area-inset-bottom))]"
                  showCloseButton
                >
                  <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-border" aria-hidden="true" />
                  <SheetHeader className="pb-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-0.5">
                        <SheetTitle className="u-serif text-lg">PH‑Eye</SheetTitle>
                        <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                          Index
                        </div>
                      </div>

                      <div className="flex items-center gap-2 pt-1">
                        <span className="inline-flex h-2 w-2 rounded-full bg-primary" aria-hidden="true" />
                        <span className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                          Live-ish
                        </span>
                      </div>
                    </div>
                  </SheetHeader>

                  <div className="space-y-2">
                    <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                      Navigate
                    </div>
                    <div className="grid gap-1.5">
                      {navItems.map((item) => {
                        const active = pathname === item.href;
                        return (
                          <SheetClose asChild key={item.href}>
                            <Link
                              href={item.href}
                              aria-current={active ? "page" : undefined}
                              className={[
                                "relative flex items-center justify-between rounded-md px-3 py-3 text-sm transition-colors",
                                "border bg-card/40 hover:bg-muted",
                                active ? "text-foreground bg-muted/70" : "text-muted-foreground hover:text-foreground",
                              ].join(" ")}
                            >
                              <span className="font-medium">{item.label}</span>
                              {active && <span className="h-1.5 w-1.5 rounded-full bg-primary" aria-hidden="true" />}
                              <span
                                aria-hidden="true"
                                className={[
                                  "absolute left-0 top-2 bottom-2 w-0.5 rounded-full bg-primary transition-opacity",
                                  active ? "opacity-100" : "opacity-0",
                                ].join(" ")}
                              />
                            </Link>
                          </SheetClose>
                        );
                      })}
                    </div>
                  </div>

                  <div className="mt-6 space-y-2">
                    <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                      Sources
                    </div>
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
                        <SheetClose asChild key={source}>
                          <Link
                            href={`/source/${encodeURIComponent(source)}`}
                            className="inline-flex items-center rounded-full border bg-card px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                          >
                            {source}
                          </Link>
                        </SheetClose>
                      ))}
                    </div>
                  </div>

                  {lastUpdated && (
                    <div className="mt-6 pt-4 border-t">
                      <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                        As of {formatDateTime(lastUpdated)}
                      </div>
                    </div>
                  )}
                </SheetContent>
              </Sheet>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
