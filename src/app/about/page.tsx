import type { Metadata } from "next";
import Link from "next/link";
import { BrainCircuit, Database, LineChart, Search, Shield, Sparkles, Users } from "lucide-react";
import MainLayout from "@/components/layout/main-layout";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export const metadata: Metadata = {
  title: "About • PH‑Eye",
  description: "How PH‑Eye collects news, runs sentiment/NER, and powers Trends, Correlation, and Entities dashboards.",
};

function SectionTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="space-y-1">
      <h2 className="u-serif text-2xl font-semibold tracking-tight">{title}</h2>
      {subtitle ? <p className="text-sm text-muted-foreground leading-6 max-w-3xl">{subtitle}</p> : null}
    </div>
  );
}

export default function AboutPage() {
  return (
    <MainLayout>
      <div className="space-y-10">
        <header className="space-y-4">
          <div className="space-y-2">
            <h1 className="u-serif text-3xl sm:text-4xl font-semibold tracking-tight">About PH‑Eye</h1>
            <p className="text-sm sm:text-base text-muted-foreground leading-6 max-w-3xl">
              PH‑Eye is an editorial analytics platform that aggregates Philippine news, runs lightweight NLP (sentiment
              + named entities), and renders dashboards to help you understand coverage patterns across sources.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className="u-mono text-[10px] uppercase tracking-widest">
              7 Sources
            </Badge>
            <Badge variant="outline" className="u-mono text-[10px] uppercase tracking-widest">
              VADER + DistilBERT
            </Badge>
            <Badge variant="outline" className="u-mono text-[10px] uppercase tracking-widest">
              spaCy NER
            </Badge>
            <Badge variant="outline" className="u-mono text-[10px] uppercase tracking-widest">
              Next.js + FastAPI + Supabase
            </Badge>
          </div>
        </header>

        <section className="space-y-4">
          <SectionTitle
            title="How It Works"
            subtitle="A simple pipeline: collect → store → analyze → snapshot → visualize. The goal is to keep the system explainable, resilient, and fast enough for demos."
          />

          <div className="grid gap-3 sm:gap-4 md:grid-cols-5">
            {[
              {
                k: "1",
                icon: <Database className="h-4 w-4" aria-hidden="true" />,
                title: "Collect",
                desc: "Scrapers fetch articles from supported PH sources.",
              },
              {
                k: "2",
                icon: <Shield className="h-4 w-4" aria-hidden="true" />,
                title: "Normalize",
                desc: "Content is cleaned + validated to reduce noise.",
              },
              {
                k: "3",
                icon: <BrainCircuit className="h-4 w-4" aria-hidden="true" />,
                title: "Analyze",
                desc: "Sentiment + NER are written as analysis rows.",
              },
              {
                k: "4",
                icon: <Sparkles className="h-4 w-4" aria-hidden="true" />,
                title: "Snapshot",
                desc: "Aggregates are precomputed for faster dashboards.",
              },
              {
                k: "5",
                icon: <LineChart className="h-4 w-4" aria-hidden="true" />,
                title: "Visualize",
                desc: "Trends, correlation, and entity rankings.",
              },
            ].map((s) => (
              <Card key={s.k} className="bg-card/70">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <div className="inline-flex items-center justify-center h-8 w-8 rounded-md border bg-background/60">
                      {s.icon}
                    </div>
                    <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">{s.k}</div>
                  </div>
                  <CardTitle className="text-sm">{s.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-muted-foreground leading-5">{s.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>

        <section className="space-y-4">
          <SectionTitle
            title="Engines (Sentiment + NER)"
            subtitle="PH‑Eye uses a hybrid sentiment approach and a standard NER model so outputs are explainable and comparable across sources."
          />

          <div className="grid gap-4 md:grid-cols-3">
            <Card className="md:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BrainCircuit className="h-4 w-4" aria-hidden="true" />
                  Hybrid Sentiment
                </CardTitle>
                <CardDescription>
                  Routing between lexicon-based VADER (with a Taglish patch) and a CPU DistilBERT SST‑2 pipeline.
                </CardDescription>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground leading-6 space-y-3">
                <p>
                  For Tagalog/Taglish-heavy text, PH‑Eye can prefer VADER with a lightweight PH lexicon patch. For more
                  English-heavy text, it can fall back to DistilBERT sentiment to reduce false-neutral outputs.
                </p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>
                    Stored in <span className="u-mono text-[12px]">bias_analysis</span> as{" "}
                    <span className="u-mono text-[12px]">model_type='sentiment'</span>.
                  </li>
                  <li>
                    Hybrid routing is heuristic (language signal + reporting preface detection), not a guaranteed
                    language ID.
                  </li>
                </ul>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-4 w-4" aria-hidden="true" />
                  spaCy NER
                </CardTitle>
                <CardDescription>Extracts PERSON / ORG / GPE to power the Entities page.</CardDescription>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground leading-6">
                Entity counts are aggregated by mention frequency, with optional average sentiment per entity based on
                associated articles.
              </CardContent>
            </Card>
          </div>
        </section>

        <section className="space-y-4">
          <SectionTitle
            title="How Each Page Works"
            subtitle="A quick guide for reading the dashboards and understanding what each view is (and isn’t) claiming."
          />

          <Tabs defaultValue="trends" className="w-full">
            <TabsList className="w-full justify-start overflow-x-auto">
              <TabsTrigger value="home">Home</TabsTrigger>
              <TabsTrigger value="search">Search</TabsTrigger>
              <TabsTrigger value="trends">Trends</TabsTrigger>
              <TabsTrigger value="correlation">Correlation</TabsTrigger>
              <TabsTrigger value="entities">Entities</TabsTrigger>
            </TabsList>

            <TabsContent value="home">
              <Card>
                <CardHeader>
                  <CardTitle>Home (Latest Feed)</CardTitle>
                  <CardDescription>Fast browsing with a Quick View for summaries and metadata.</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground leading-6 space-y-2">
                  <ul className="list-disc pl-5 space-y-1">
                    <li>Shows the newest scraped articles, grouped by source.</li>
                    <li>Quick View lets you skim content and jump to the original article.</li>
                    <li>Sentiment badges reflect the latest sentiment row stored for the article.</li>
                  </ul>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="search">
              <Card>
                <CardHeader>
                  <CardTitle>Search</CardTitle>
                  <CardDescription>Keyword search across articles (with database-side optimizations when enabled).</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground leading-6 space-y-2">
                  <ul className="list-disc pl-5 space-y-1">
                    <li>Uses Supabase/Postgres queries to retrieve matching articles.</li>
                    <li>
                      For best performance at scale, enable Postgres full‑text search (FTS) so the UI can use{" "}
                      <span className="u-mono text-[12px]">textSearch</span> instead of slow{" "}
                      <span className="u-mono text-[12px]">ILIKE %...%</span> scans.
                    </li>
                  </ul>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="trends">
              <Card>
                <CardHeader>
                  <CardTitle>Trends (Sentiment Over Time)</CardTitle>
                  <CardDescription>Daily sentiment distribution + averages for a selected period.</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground leading-6 space-y-2">
                  <ul className="list-disc pl-5 space-y-1">
                    <li>Charts show counts and percentages per day (positive / neutral / negative).</li>
                    <li>Use period filters (7d/30d) to compare short vs longer coverage patterns.</li>
                    <li>In demo mode, trends can load from Supabase snapshot tables for speed and reliability.</li>
                  </ul>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="correlation">
              <Card>
                <CardHeader>
                  <CardTitle>Correlation (Cross‑Source Similarity)</CardTitle>
                  <CardDescription>A Pearson correlation heatmap across sources using daily average sentiment.</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground leading-6 space-y-2">
                  <ul className="list-disc pl-5 space-y-1">
                    <li>
                      Values closer to <span className="u-mono text-[12px]">+1</span> mean two sources move together;{" "}
                      closer to <span className="u-mono text-[12px]">-1</span> means they move in opposite directions.
                    </li>
                    <li>Correlation doesn’t prove causation; it’s a directional signal for “similar tone”.</li>
                    <li>Use it to spot outliers and investigate days where sources diverge.</li>
                  </ul>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="entities">
              <Card>
                <CardHeader>
                  <CardTitle>Entities (Who/What Is Being Talked About)</CardTitle>
                  <CardDescription>Top entities by mention volume, with optional average sentiment.</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground leading-6 space-y-2">
                  <ul className="list-disc pl-5 space-y-1">
                    <li>Ranks entities extracted via NER (PERSON / ORG / GPE).</li>
                    <li>Mentions count reflects frequency, not importance or truth.</li>
                    <li>Average sentiment is derived from related article sentiment, so it inherits model limitations.</li>
                  </ul>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </section>

        <section className="space-y-4">
          <SectionTitle title="Tech Stack" subtitle="Tools are chosen for reliability, debuggability, and fast iteration." />

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4" aria-hidden="true" />
                  Frontend
                </CardTitle>
                <CardDescription>Next.js App Router + TypeScript UI dashboards.</CardDescription>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground leading-6">
                Next.js, React, TypeScript, Tailwind CSS, shadcn/ui, Recharts, Supabase JS.
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Search className="h-4 w-4" aria-hidden="true" />
                  Backend + Infra
                </CardTitle>
                <CardDescription>Scraping + ML pipeline + storage.</CardDescription>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground leading-6 space-y-2">
                <div>FastAPI, Celery, Redis, Playwright, BeautifulSoup/lxml.</div>
                <div>Supabase (Postgres) stores articles, analysis rows, and snapshots.</div>
              </CardContent>
            </Card>
          </div>
        </section>

        <section className="space-y-4">
          <SectionTitle
            title="Notes (Demo Mode vs Full Mode)"
            subtitle="PH‑Eye can run as a full stack locally, or as a frontend-only demo that reads precomputed snapshots from Supabase."
          />
          <Card>
            <CardContent className="pt-6 text-sm text-muted-foreground leading-6 space-y-2">
              <p>
                If the FastAPI backend isn’t deployed, the dashboards can still work by reading snapshot tables written
                by scheduled jobs (e.g. GitHub Actions cron). This keeps the UI responsive even on slower connections.
              </p>
              <p>
                Learn more in{" "}
                <Link href="/#demo-mode" className="underline underline-offset-4">
                  README demo mode
                </Link>{" "}
                (if available), or run the full pipeline locally with Docker Compose.
              </p>
            </CardContent>
          </Card>
        </section>
      </div>
    </MainLayout>
  );
}

