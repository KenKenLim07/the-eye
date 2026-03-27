"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { cn } from "@/lib/utils";
import { formatDateTime } from "@/lib/utils/date";
import { ExternalLink, Flag, Loader2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

export type QuickViewArticle = {
  id: string | number;
  title: string;
  content: string | null;
  source: string;
  category: string | null;
  published_at: string | null;
  url: string | null;
  sentiment?: string | null;
};

const REPORT_NOTE_MAX_LEN = 200;

function sentimentClass(sentiment: string | null | undefined): string {
  const v = (sentiment || "").toLowerCase();
  if (v === "positive") return "bg-emerald-600 text-white border-transparent dark:bg-emerald-500";
  if (v === "negative") return "bg-red-600 text-white border-transparent dark:bg-red-500";
  if (v === "neutral") return "bg-slate-700 text-white border-transparent dark:bg-slate-500";
  return "bg-muted text-muted-foreground border-border";
}

function uuidV4(): string {
  const c: Crypto | undefined =
    typeof globalThis !== "undefined" ? (globalThis.crypto as Crypto | undefined) : undefined;

  // Prefer native randomUUID when available.
  if (c?.randomUUID) return c.randomUUID();

  // Fallback: generate v4 UUID from random bytes.
  const bytes = new Uint8Array(16);
  if (c?.getRandomValues) {
    c.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) {
      bytes[i] = Math.floor(Math.random() * 256);
    }
  }

  // Set version (4) and variant bits.
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;

  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export default function ArticleQuickViewDialog(props: {
  article: QuickViewArticle | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { article, open, onOpenChange } = props;
  const content = (article?.content || "").trim();
  const looksLikeExcerpt = /\.\.\.$|…$/.test(content);
  const articleIdKey = article?.id != null ? String(article.id) : null;
  const reportedStorageKey = articleIdKey ? `ph-eye:reported_sentiment:${articleIdKey}` : null;

  const [reportOpen, setReportOpen] = useState(false);
  const [reportType, setReportType] = useState<"sentiment" | "not_news">("sentiment");
  const [reportedLabel, setReportedLabel] = useState<"positive" | "neutral" | "negative">("neutral");
  const [reportNote, setReportNote] = useState("");
  const [reportStatus, setReportStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [reportError, setReportError] = useState<string | null>(null);
  const [hasReported, setHasReported] = useState(false);

  const locationPath = useMemo(() => {
    if (typeof window === "undefined") return null;
    return `${window.location.pathname}${window.location.search || ""}`;
  }, []);

  useEffect(() => {
    if (!reportedStorageKey) {
      setHasReported(false);
      return;
    }
    try {
      setHasReported(window.localStorage.getItem(reportedStorageKey) === "1");
    } catch {
      setHasReported(false);
    }
  }, [reportedStorageKey]);

  useEffect(() => {
    if (!reportOpen) {
      setReportStatus("idle");
      setReportError(null);
      setReportNote("");
      setReportType("sentiment");
      setReportedLabel("neutral");
    }
  }, [reportOpen]);

  async function submitReport() {
    if (!articleIdKey) return;
    if (hasReported) return;
    setReportStatus("submitting");
    setReportError(null);
    const clientReportId = uuidV4();

    try {
      const res = await fetch("/api/reports/sentiment", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          article_id: articleIdKey,
          report_type: reportType,
          reported_label: reportType === "sentiment" ? reportedLabel : undefined,
          note: reportNote || undefined,
          client_report_id: clientReportId,
          context_path: locationPath || undefined,
        }),
      });
      const json = (await res.json().catch(() => null)) as { ok?: boolean; error?: string } | null;
      if (!res.ok || !json?.ok) {
        throw new Error(json?.error || `Request failed (HTTP ${res.status})`);
      }
      if (reportedStorageKey) {
        try {
          window.localStorage.setItem(reportedStorageKey, "1");
        } catch {
          // ignore
        }
      }
      setHasReported(true);
      setReportStatus("success");
      window.setTimeout(() => setReportOpen(false), 650);
    } catch (e) {
      setReportStatus("error");
      setReportError(e instanceof Error ? e.message : "Failed to submit report.");
    }
  }

  const optionButtonClass = (active: boolean) =>
    cn(
      "h-11 rounded-md border px-3 text-sm font-medium transition-colors",
      "hover:bg-muted/30",
      active
        ? "bg-foreground text-background border-foreground"
        : "bg-background text-foreground border-border"
    );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className={cn(
          "p-0 overflow-hidden !flex !flex-col",
          "w-full max-w-[calc(100%-1.25rem)] sm:max-w-3xl",
          "max-h-[92dvh] duration-150"
        )}
        onCloseAutoFocus={(e) => e.preventDefault()}
      >
        <div className="flex items-start justify-between gap-3 border-b bg-background px-3 sm:px-4 py-3">
          <div className="min-w-0 flex-1">
            <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Quick view</div>
            <div className="u-serif text-lg sm:text-2xl font-semibold leading-tight break-words">
              {article?.title ?? ""}
            </div>

            <div className="mt-2 flex items-center gap-2 flex-wrap">
              {article?.source ? (
                <Badge variant="outline" className="u-mono uppercase tracking-widest text-[10px]">
                  {article.source}
                </Badge>
              ) : null}
              {article?.category ? (
                <Badge variant="secondary" className="u-mono uppercase tracking-widest text-[10px]">
                  {article.category}
                </Badge>
              ) : null}
              {article?.published_at ? (
                <Badge variant="outline" className="u-mono uppercase tracking-widest text-[10px]">
                  {formatDateTime(article.published_at)}
                </Badge>
              ) : null}
              {article?.sentiment ? (
                <Badge
                  variant="outline"
                  className={cn("u-mono uppercase tracking-wide text-[10px]", sentimentClass(article.sentiment))}
                  title={`VADER sentiment: ${article.sentiment}`}
                >
                  {article.sentiment}
                </Badge>
              ) : (
                <Badge variant="outline" className="u-mono uppercase tracking-widest text-[10px] text-muted-foreground">
                  unlabeled
                </Badge>
              )}
              {article?.id != null ? (
                <span className="u-mono text-[10px] tracking-widest text-muted-foreground/70" title={`Article ID ${article.id}`}>
                  #{article.id}
                </span>
              ) : null}
            </div>
          </div>

          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-11 w-11 shrink-0"
            onClick={() => onOpenChange(false)}
            aria-label="Close quick view"
            title="Close"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto overscroll-contain min-h-0 px-3 sm:px-4 py-4">
          <div className="prose prose-sm max-w-none">
            <p className="text-sm leading-7 whitespace-pre-wrap break-words text-foreground">
              {article?.content || "No summary available."}
            </p>
            {article?.url && looksLikeExcerpt ? (
              <div className="mt-4 rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                This summary looks truncated for this source. Use “Read original” for the full story.
              </div>
            ) : null}
          </div>
        </div>

        {article?.url ? (
          <div className="border-t px-3 sm:px-4 py-3 bg-background">
            <div className="flex flex-row gap-2">
              <Dialog open={reportOpen} onOpenChange={setReportOpen}>
                <Button
                  type="button"
                  variant="outline"
                  className="h-11 flex-1"
                  onClick={() => setReportOpen(true)}
                  disabled={!articleIdKey || hasReported}
                  title={hasReported ? "Thanks — already reported for this article on this device." : "Report an issue"}
                >
                  <Flag className="h-4 w-4" />
                  {hasReported ? "Reported" : "Report"}
                </Button>

                <DialogContent className="sm:max-w-md">
                  <DialogHeader>
                    <DialogTitle>Report</DialogTitle>
                    <DialogDescription>
                      Help us fine-tune DistilBERT and our modified VADER by flagging misclassifications and non-news.
                    </DialogDescription>
                  </DialogHeader>

                  <div className="space-y-3">
                    <div className="space-y-2">
                      <div className="text-sm font-medium">Type</div>
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          type="button"
                          onClick={() => setReportType("sentiment")}
                          className={optionButtonClass(reportType === "sentiment")}
                          aria-pressed={reportType === "sentiment"}
                        >
                          Sentiment wrong
                        </button>
                        <button
                          type="button"
                          onClick={() => setReportType("not_news")}
                          className={optionButtonClass(reportType === "not_news")}
                          aria-pressed={reportType === "not_news"}
                        >
                          Ad / not news
                        </button>
                      </div>
                    </div>

                    {reportType === "sentiment" ? (
                    <div className="space-y-2">
                      <div className="text-sm font-medium">Correct label</div>
                      <div className="grid grid-cols-2 gap-2">
                        {(
                          [
                            { value: "positive", label: "Positive" },
                            { value: "neutral", label: "Neutral" },
                            { value: "negative", label: "Negative" },
                          ] as const
                        ).map((opt) => (
                          <button
                            key={opt.value}
                            type="button"
                            onClick={() => setReportedLabel(opt.value)}
                            className={optionButtonClass(reportedLabel === opt.value)}
                            aria-pressed={reportedLabel === opt.value}
                          >
                            {opt.label}
                          </button>
                        ))}
                      </div>
                    </div>
                    ) : null}

                    <div className="space-y-2">
                      <div className="text-sm font-medium">Note (optional)</div>
                      <Textarea
                        value={reportNote}
                        onChange={(e) => setReportNote(e.target.value)}
                        placeholder={reportType === "not_news" ? "What did we pick up? (e.g. advertisement/promo)" : "What’s wrong with the sentiment label?"}
                        maxLength={REPORT_NOTE_MAX_LEN}
                      />
                      <div className="text-xs text-muted-foreground">{Math.min(REPORT_NOTE_MAX_LEN, reportNote.length)}/{REPORT_NOTE_MAX_LEN}</div>
                    </div>

                    {reportStatus === "success" ? (
                      <Alert>
                        <AlertDescription>Thanks — report submitted.</AlertDescription>
                      </Alert>
                    ) : reportStatus === "error" ? (
                      <Alert className="border-foreground/20 bg-muted/20 text-foreground">
                        <AlertDescription>{reportError || "Failed to submit report."}</AlertDescription>
                      </Alert>
                    ) : null}
                  </div>

                  <DialogFooter>
                    <Button type="button" variant="outline" onClick={() => setReportOpen(false)} className="h-11">
                      Cancel
                    </Button>
                    <Button
                      type="button"
                      onClick={submitReport}
                      className="h-11"
                      disabled={!articleIdKey || hasReported || reportStatus === "submitting"}
                    >
                      {reportStatus === "submitting" ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                      Submit
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>

              <Button asChild className="h-11 flex-1">
                <a href={article.url} target="_blank" rel="noreferrer">
                  <ExternalLink className="h-4 w-4" />
                  Read original
                </a>
              </Button>
            </div>
          </div>
        ) : (
          <div className="border-t px-3 sm:px-4 py-3 bg-background">
            <Dialog open={reportOpen} onOpenChange={setReportOpen}>
              <Button
                type="button"
                variant="outline"
                className="h-11 w-full"
                onClick={() => setReportOpen(true)}
                disabled={!articleIdKey || hasReported}
                title={hasReported ? "Thanks — already reported for this article on this device." : "Report an issue"}
              >
                <Flag className="h-4 w-4" />
                {hasReported ? "Reported" : "Report"}
              </Button>

              <DialogContent className="sm:max-w-md">
                <DialogHeader>
                  <DialogTitle>Report</DialogTitle>
                  <DialogDescription>
                    Help us fine-tune DistilBERT and our modified VADER by flagging misclassifications and non-news.
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-3">
                  <div className="space-y-2">
                    <div className="text-sm font-medium">Type</div>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => setReportType("sentiment")}
                        className={optionButtonClass(reportType === "sentiment")}
                        aria-pressed={reportType === "sentiment"}
                      >
                        Sentiment wrong
                      </button>
                      <button
                        type="button"
                        onClick={() => setReportType("not_news")}
                        className={optionButtonClass(reportType === "not_news")}
                        aria-pressed={reportType === "not_news"}
                      >
                        Ad / not news
                      </button>
                    </div>
                  </div>

                  {reportType === "sentiment" ? (
                  <div className="space-y-2">
                    <div className="text-sm font-medium">Correct label</div>
                    <div className="grid grid-cols-2 gap-2">
                      {(
                        [
                          { value: "positive", label: "Positive" },
                          { value: "neutral", label: "Neutral" },
                          { value: "negative", label: "Negative" },
                        ] as const
                      ).map((opt) => (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => setReportedLabel(opt.value)}
                          className={optionButtonClass(reportedLabel === opt.value)}
                          aria-pressed={reportedLabel === opt.value}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  ) : null}

                  <div className="space-y-2">
                    <div className="text-sm font-medium">Note (optional)</div>
                    <Textarea
                      value={reportNote}
                      onChange={(e) => setReportNote(e.target.value)}
                      placeholder={reportType === "not_news" ? "What did we pick up? (e.g. advertisement/promo)" : "What’s wrong with the sentiment label?"}
                      maxLength={REPORT_NOTE_MAX_LEN}
                    />
                    <div className="text-xs text-muted-foreground">{Math.min(REPORT_NOTE_MAX_LEN, reportNote.length)}/{REPORT_NOTE_MAX_LEN}</div>
                  </div>

                  {reportStatus === "success" ? (
                    <Alert>
                      <AlertDescription>Thanks — report submitted.</AlertDescription>
                    </Alert>
                  ) : reportStatus === "error" ? (
                    <Alert className="border-foreground/20 bg-muted/20 text-foreground">
                      <AlertDescription>{reportError || "Failed to submit report."}</AlertDescription>
                    </Alert>
                  ) : null}
                </div>

                <DialogFooter>
                  <Button type="button" variant="outline" onClick={() => setReportOpen(false)} className="h-11">
                    Cancel
                  </Button>
                  <Button
                    type="button"
                    onClick={submitReport}
                    className="h-11"
                    disabled={!articleIdKey || hasReported || reportStatus === "submitting"}
                  >
                    {reportStatus === "submitting" ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                    Submit
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
