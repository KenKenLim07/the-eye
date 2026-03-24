import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const fontBody = localFont({
  variable: "--font-body",
  display: "swap",
  src: [
    { path: "../fonts/PublicSans-400.woff2", weight: "400", style: "normal" },
    { path: "../fonts/PublicSans-500.woff2", weight: "500", style: "normal" },
    { path: "../fonts/PublicSans-600.woff2", weight: "600", style: "normal" },
  ],
});

const fontHead = localFont({
  variable: "--font-head",
  display: "swap",
  src: [
    { path: "../fonts/Newsreader-400.woff2", weight: "400", style: "normal" },
    { path: "../fonts/Newsreader-600.woff2", weight: "600", style: "normal" },
    { path: "../fonts/Newsreader-700.woff2", weight: "700", style: "normal" },
  ],
});

const fontCode = localFont({
  variable: "--font-code",
  display: "swap",
  src: [
    { path: "../fonts/JetBrainsMono-400.woff2", weight: "400", style: "normal" },
    { path: "../fonts/JetBrainsMono-500.woff2", weight: "500", style: "normal" },
  ],
});

export const metadata: Metadata = {
  title: "Philippine News - Latest Headlines",
  description: "Latest headlines aggregated from top Philippine news sources",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning style={{ colorScheme: "light" }}>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
(() => {
  try {
    const stored = localStorage.getItem('theme');
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    const useDark = stored ? stored === 'dark' : prefersDark;
    document.documentElement.classList.toggle('dark', useDark);
    document.documentElement.style.colorScheme = useDark ? 'dark' : 'light';
  } catch {}
})();
            `.trim(),
          }}
        />
      </head>
      <body
        className={`${fontBody.variable} ${fontHead.variable} ${fontCode.variable} antialiased font-sans`}
        suppressHydrationWarning={true}
      >
        {children}
      </body>
    </html>
  );
}
