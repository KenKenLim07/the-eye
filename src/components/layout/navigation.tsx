"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Menu, Search, X } from "lucide-react";

export default function Navigation() {
  const pathname = usePathname();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

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

  const toggleMobileMenu = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  const closeMobileMenu = () => {
    setIsMobileMenuOpen(false);
  };

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

  return (
    <nav className="sticky top-0 z-50 border-b bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/65">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex-shrink-0">
            <Link 
              href="/" 
              className="flex items-center gap-3"
              onClick={closeMobileMenu}
            >
              <div className="h-9 w-9 rounded-lg border bg-card flex items-center justify-center">
                <span className="u-mono text-xs font-semibold tracking-widest text-primary">PH</span>
              </div>
              <div className="leading-none">
                <div className="u-serif text-lg font-semibold tracking-tight">PH-Eye</div>
                <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">News Intelligence</div>
              </div>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-8">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  pathname === item.href
                    ? "text-foreground bg-accent/10"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent/5"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </div>

          <div className="flex items-center gap-3">
            {lastUpdated && (
              <div className="hidden lg:block u-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                As of {lastUpdated}
              </div>
            )}

            <Link
              href="/search"
              className="hidden md:inline-flex items-center justify-center h-9 w-9 rounded-md border bg-card hover:bg-accent/5 transition-colors"
              aria-label="Search"
            >
              <Search className="h-4 w-4" />
            </Link>

            {/* Mobile menu button */}
            <div className="md:hidden">
            <button
              onClick={toggleMobileMenu}
              className="inline-flex items-center justify-center h-10 w-10 rounded-md border bg-card hover:bg-accent/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors"
              aria-expanded={isMobileMenuOpen}
              aria-label="Toggle navigation menu"
            >
              {isMobileMenuOpen ? (
                <X className="block h-6 w-6" aria-hidden="true" />
              ) : (
                <Menu className="block h-6 w-6" aria-hidden="true" />
              )}
            </button>
          </div>
          </div>
        </div>

        {/* Mobile Navigation Menu */}
        {isMobileMenuOpen && (
          <div className="md:hidden">
            <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3 bg-background border-t">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={closeMobileMenu}
                  className={`block px-3 py-2 rounded-md text-base font-medium transition-colors ${
                    pathname === item.href
                      ? "text-foreground bg-accent/10"
                      : "text-muted-foreground hover:text-foreground hover:bg-accent/5"
                  }`}
                >
                  {item.label}
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
