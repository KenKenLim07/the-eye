import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="py-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Quick Links */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">Quick Links</h3>
              <div className="space-y-2">
                <Link href="/" className="block text-xs text-muted-foreground hover:text-foreground transition-colors">
                  Home
                </Link>
                <Link href="/sources" className="block text-xs text-muted-foreground hover:text-foreground transition-colors">
                  News Sources
                </Link>
                <Link href="/about" className="block text-xs text-muted-foreground hover:text-foreground transition-colors">
                  About
                </Link>
              </div>
            </div>

            {/* Sources */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">Sources</h3>
              <div className="grid grid-cols-2 gap-1 text-xs text-muted-foreground">
                <span>GMA News</span>
                <span>Rappler</span>
                <span>Inquirer</span>
                <span>Philstar</span>
                <span>Sunstar</span>
                <span>Manila Bulletin</span>
              </div>
            </div>
          </div>

          <div className="mt-8 pt-6 border-t">
            <div className="flex flex-col sm:flex-row justify-between items-center space-y-2 sm:space-y-0">
              <p className="text-xs text-muted-foreground">
                © 2024 ph-eye. A Philippine news aggregation platform.
              </p>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
} 