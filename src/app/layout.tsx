import type { Metadata } from "next";
import "./globals.css";

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
    <html lang="en">
      <body
        className="antialiased"
        suppressHydrationWarning={true}
      >
        {children}
      </body>
    </html>
  );
}
