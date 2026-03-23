"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Menu, Moon, Search, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetClose, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

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
    fetch("/api/articles?pageSize=1")
      .then((r) => r.json())
      .then((json) => {
        if (cancelled) return;
        const ts = json?.data?.[0]?.published_at as string | null | undefined;
        if (!ts) return;
        const d = new Date(ts);
        if (Number.isNaN(d.getTime())) return;
        setLastUpdated(d.toLocaleString());
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
                As of {lastUpdated}
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
                    className="h-11 w-11"
                    aria-label="Open menu"
                  >
                    <Menu className="h-5 w-5" />
                  </Button>
                </SheetTrigger>

                <SheetContent side="right" className="p-4 sm:p-5" showCloseButton>
                  <SheetHeader className="pb-2">
                    <SheetTitle className="u-serif text-lg">PH‑Eye</SheetTitle>
                    {lastUpdated && (
                      <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                        As of {lastUpdated}
                      </div>
                    )}
                  </SheetHeader>

                  <form action="/search" method="get" className="mt-3 flex items-center gap-2">
                    <Input
                      name="q"
                      placeholder="Search headlines…"
                      className="h-11"
                      aria-label="Search headlines"
                    />
                    <Button type="submit" className="h-11 px-3">
                      <Search className="h-4 w-4" />
                      <span className="sr-only">Search</span>
                    </Button>
                  </form>

                  <div className="mt-5 space-y-2">
                    <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                      Navigate
                    </div>
                    <div className="grid gap-1">
                      {navItems.map((item) => {
                        const active = pathname === item.href;
                        return (
                          <SheetClose asChild key={item.href}>
                            <Link
                              href={item.href}
                              className={[
                                "flex items-center justify-between rounded-md px-3 py-2.5 text-sm transition-colors",
                                active
                                  ? "bg-accent/10 text-foreground"
                                  : "text-muted-foreground hover:bg-accent/5 hover:text-foreground",
                              ].join(" ")}
                            >
                              <span className="font-medium">{item.label}</span>
                              {active && (
                                <span className="u-mono text-[10px] uppercase tracking-widest text-primary">
                                  Here
                                </span>
                              )}
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
                            className="inline-flex items-center rounded-full border bg-card px-3 py-1.5 text-xs text-muted-foreground hover:bg-accent/5 hover:text-foreground transition-colors"
                          >
                            {source}
                          </Link>
                        </SheetClose>
                      ))}
                    </div>
                  </div>

                  <div className="mt-auto pt-6">
                    <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                      Tip
                    </div>
                    <div className="text-sm text-muted-foreground leading-6">
                      Use Search to filter by keywords or jump into a specific source.
                    </div>
                  </div>
                </SheetContent>
              </Sheet>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
