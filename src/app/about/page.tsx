import type { Metadata } from "next";
import Link from "next/link";
import { BrainCircuit, Database, LineChart, Search, Shield, Sparkles, Users } from "lucide-react";
import MainLayout from "@/components/layout/main-layout";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export const metadata: Metadata = {
  title: "About • PH VibeCheck AI",
  description: "How PH VibeCheck AI collects news, runs sentiment/NER, and powers Trends, Correlation, and Entities dashboards.",
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
            <h1 className="u-serif text-3xl sm:text-4xl font-semibold tracking-tight">About PH VibeCheck AI</h1>
            <p className="text-sm sm:text-base text-muted-foreground leading-6 max-w-3xl">
              PH VibeCheck AI is an editorial analytics platform that aggregates Philippine news, runs lightweight NLP
              (sentiment + named entities), and renders dashboards to help you understand coverage patterns across sources.
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
            subtitle="PH VibeCheck AI uses a hybrid sentiment approach and a standard NER model so outputs are explainable and comparable across sources."
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
                  For Tagalog/Taglish-heavy text, PH VibeCheck AI can prefer VADER with a lightweight PH lexicon patch. For more
                  English-heavy text, it can fall back to DistilBERT sentiment to reduce false-neutral outputs.
                </p>
                <ul className="list-disc pl-5 space-y-1">
                  <li>
                    Stored in <span className="u-mono text-[12px]">bias_analysis</span> as{" "}
                    <span className="u-mono text-[12px]">model_type=&apos;sentiment&apos;</span>.
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
            subtitle="A quick guide you can read two ways: plain-English for non-tech viewers, plus technical notes for methods/implementation."
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
                  <CardDescription>Fast browsing with Quick View for context and details.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-2">
                  <Card className="bg-card/60">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">How it works</CardTitle>
                      <CardDescription>What you should expect to see.</CardDescription>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground leading-6 space-y-2">
                      <ul className="list-disc pl-5 space-y-1">
                        <li>The newest headlines from each news source.</li>
                        <li>Tap Quick View to read a short summary and the article details.</li>
                        <li>Tap Read original to open the full story from the publisher.</li>
                      </ul>
                    </CardContent>
                  </Card>

                  <Card className="bg-card/60">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">Technical</CardTitle>
                      <CardDescription>How it is produced.</CardDescription>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground leading-6 space-y-2">
                      <ul className="list-disc pl-5 space-y-1">
                        <li>Lists recent rows from <span className="u-mono text-[12px]">articles</span>.</li>
                        <li>Sentiment badge uses the latest stored sentiment row for that article when available.</li>
                        <li>Quick View is a UI dialog; it does not modify the original content.</li>
                      </ul>
                    </CardContent>
                  </Card>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="search">
              <Card>
                <CardHeader>
                  <CardTitle>Search</CardTitle>
                  <CardDescription>Find articles by keywords, then open Quick View or the original link.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-2">
                  <Card className="bg-card/60">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">How it works</CardTitle>
                      <CardDescription>What it does.</CardDescription>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground leading-6 space-y-2">
                      <ul className="list-disc pl-5 space-y-1">
                        <li>Type a keyword (person, place, topic) to find related news.</li>
                        <li>Results help you quickly compare how different sources cover the same topic.</li>
                        <li>If nothing shows up, try shorter keywords or different spelling.</li>
                      </ul>
                    </CardContent>
                  </Card>

                  <Card className="bg-card/60">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">Technical</CardTitle>
                      <CardDescription>How it stays fast.</CardDescription>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground leading-6 space-y-2">
                      <ul className="list-disc pl-5 space-y-1">
                        <li>Search runs in Postgres (Supabase) against article text fields.</li>
                        <li>For scale, prefer full‑text search (FTS) over <span className="u-mono text-[12px]">ILIKE</span> scans.</li>
                        <li>Indexes determine whether search stays snappy or times out.</li>
                      </ul>
                    </CardContent>
                  </Card>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="trends">
              <Card>
                <CardHeader>
                  <CardTitle>Trends (Sentiment Over Time)</CardTitle>
                  <CardDescription>Shows how the overall “tone” changes day by day.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-2">
                  <Card className="bg-card/60">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">How it works</CardTitle>
                      <CardDescription>How to read it.</CardDescription>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground leading-6 space-y-2">
                      <ul className="list-disc pl-5 space-y-1">
                        <li>Each day is summarized into Positive, Neutral, and Negative counts.</li>
                        <li>Spikes can mean a major event (disaster, crime, sports win, policy news).</li>
                        <li>Use 7 days for recent changes; 30 days for broader patterns.</li>
                      </ul>
                    </CardContent>
                  </Card>

                  <Card className="bg-card/60">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">Technical</CardTitle>
                      <CardDescription>How it is computed.</CardDescription>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground leading-6 space-y-2">
                      <ul className="list-disc pl-5 space-y-1">
                        <li>Each article gets a sentiment label from the NLP pipeline.</li>
                        <li>Daily totals are aggregated by publish date and label distribution.</li>
                        <li>In demo mode, the chart reads from snapshot tables for stability on Vercel.</li>
                      </ul>
                    </CardContent>
                  </Card>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="correlation">
              <Card>
                <CardHeader>
                  <CardTitle>Correlation (Cross‑Source Similarity)</CardTitle>
                  <CardDescription>Compares how similar different sources feel over the same time window.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-2">
                  <Card className="bg-card/60">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">How it works</CardTitle>
                      <CardDescription>What the heatmap means.</CardDescription>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground leading-6 space-y-2">
                      <ul className="list-disc pl-5 space-y-1">
                        <li>Brighter/stronger cells mean two sources “move together” more often.</li>
                        <li>Negative values mean they tend to move in opposite directions.</li>
                        <li>Use it as a clue, then open articles to see why they differ.</li>
                      </ul>
                    </CardContent>
                  </Card>

                  <Card className="bg-card/60">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">Technical</CardTitle>
                      <CardDescription>How similarity is measured.</CardDescription>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground leading-6 space-y-2">
                      <ul className="list-disc pl-5 space-y-1">
                        <li>Uses Pearson correlation on daily average sentiment scores per source.</li>
                        <li>Only overlapping days are comparable; missing days reduce confidence.</li>
                        <li>Correlation is not causation; it is a statistical similarity signal.</li>
                      </ul>
                    </CardContent>
                  </Card>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="entities">
              <Card>
                <CardHeader>
                  <CardTitle>Entities (Who/What Is Being Talked About)</CardTitle>
                  <CardDescription>Shows the most-mentioned people, organizations, and places.</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-2">
                  <Card className="bg-card/60">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">How it works</CardTitle>
                      <CardDescription>What rankings show.</CardDescription>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground leading-6 space-y-2">
                      <ul className="list-disc pl-5 space-y-1">
                        <li>Higher rank means the name/place shows up in more articles.</li>
                        <li>It measures “how often mentioned,” not whether the topic is good or bad.</li>
                        <li>Use it to spot dominant topics and compare across time periods.</li>
                        <li>
                          If you see an entity sentiment score, it’s an average based on the sentiment of articles
                          where that entity was mentioned.
                        </li>
                      </ul>
                    </CardContent>
                  </Card>

                  <Card className="bg-card/60">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm">Technical</CardTitle>
                      <CardDescription>How entities are extracted.</CardDescription>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground leading-6 space-y-2">
                      <ul className="list-disc pl-5 space-y-1">
                        <li>Runs NER to extract PERSON/ORG/GPE tokens from article text.</li>
                        <li>Aggregates mentions into a ranked list for the selected window.</li>
                        <li>
                          Entity sentiment is computed by linking each entity mention back to the articles it appears
                          in, then averaging those articles’ sentiment scores/labels.
                        </li>
                        <li>
                          Because it’s derived from article sentiment, entity sentiment can be noisy (especially for
                          mixed or purely factual reporting).
                        </li>
                      </ul>
                    </CardContent>
                  </Card>
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
            subtitle="PH VibeCheck AI can run as a full stack locally, or as a frontend-only demo that reads precomputed snapshots from Supabase."
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
