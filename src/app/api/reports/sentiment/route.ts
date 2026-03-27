import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import { getSupabaseAdmin, getSupabaseAdminUntyped } from "@/lib/supabase/admin";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_NOTE_LEN = 200;
const MAX_REPORTS_PER_HOUR = 5;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const REPORT_TYPES = new Set(["sentiment", "not_news"]);

function firstIpFromXff(xff: string | null): string | null {
  if (!xff) return null;
  const first = xff.split(",")[0]?.trim();
  return first || null;
}

function sha256Hex(input: string): string {
  return crypto.createHash("sha256").update(input).digest("hex");
}

function hashIp(ip: string, salt: string | undefined): string {
  const s = salt || "";
  return sha256Hex(`${s}|${ip}`);
}

function safeContextPath(referer: string | null): string | null {
  if (!referer) return null;
  try {
    const u = new URL(referer);
    const path = `${u.pathname}${u.search || ""}`;
    if (!path || path.length > 300) return null;
    return path;
  } catch {
    return null;
  }
}

function isValidReportedLabel(v: unknown): v is "positive" | "neutral" | "negative" {
  return v === "positive" || v === "neutral" || v === "negative";
}

export async function POST(req: NextRequest) {
  try {
    const supabaseAdmin = getSupabaseAdmin();
    const supabaseAdminUntyped = getSupabaseAdminUntyped();

    const body = (await req.json().catch(() => null)) as
      | {
          article_id?: unknown;
          report_type?: unknown;
          reported_label?: unknown;
          note?: unknown;
          client_report_id?: unknown;
          context_path?: unknown;
        }
      | null;

    const articleIdRaw = body?.article_id;
    const reportTypeRaw = body?.report_type;
    const reportedLabel = body?.reported_label;
    const noteRaw = body?.note;
    const clientReportId = body?.client_report_id;
    const contextPathRaw = body?.context_path;

    const articleId =
      typeof articleIdRaw === "number"
        ? Math.trunc(articleIdRaw)
        : typeof articleIdRaw === "string"
          ? Number.parseInt(articleIdRaw, 10)
          : NaN;

    if (!Number.isFinite(articleId) || articleId <= 0) {
      return NextResponse.json({ ok: false, error: "Invalid article_id" }, { status: 400 });
    }

    const reportType = typeof reportTypeRaw === "string" ? reportTypeRaw.trim() : "sentiment";
    if (!REPORT_TYPES.has(reportType)) {
      return NextResponse.json({ ok: false, error: "Invalid report_type" }, { status: 400 });
    }
    if (reportType === "sentiment" && !isValidReportedLabel(reportedLabel)) {
      return NextResponse.json({ ok: false, error: "Invalid reported_label" }, { status: 400 });
    }
    if (typeof clientReportId !== "string" || clientReportId.length < 10 || clientReportId.length > 80) {
      return NextResponse.json({ ok: false, error: "Invalid client_report_id" }, { status: 400 });
    }
    if (!UUID_RE.test(clientReportId)) {
      return NextResponse.json({ ok: false, error: "client_report_id must be a UUID" }, { status: 400 });
    }

    let note: string | null = null;
    if (typeof noteRaw === "string") {
      note = noteRaw.trim();
      if (note.length === 0) note = null;
      if (note && note.length > MAX_NOTE_LEN) {
        return NextResponse.json({ ok: false, error: `Note too long (max ${MAX_NOTE_LEN})` }, { status: 400 });
      }
    }

    const xff = req.headers.get("x-forwarded-for");
    const xreal = req.headers.get("x-real-ip");
    const ip = firstIpFromXff(xff) || (xreal ? xreal.trim() : null);
    const ipHashSalt = process.env.REPORT_IP_HASH_SALT;
    const reporterIpHash = ip ? hashIp(ip, ipHashSalt) : null;

    let contextPath: string | null = null;
    if (typeof contextPathRaw === "string") {
      const trimmed = contextPathRaw.trim();
      if (trimmed && trimmed.length <= 300) contextPath = trimmed;
    }
    if (!contextPath) {
      contextPath = safeContextPath(req.headers.get("referer"));
    }
    const userAgent = (req.headers.get("user-agent") || "").slice(0, 400) || null;

    // Rate limit (best-effort) by IP hash.
    if (reporterIpHash) {
      const since = new Date(Date.now() - 60 * 60 * 1000).toISOString();
      const { count, error: countErr } = await supabaseAdminUntyped
        .from("sentiment_misclassification_reports")
        .select("id", { head: true, count: "exact" })
        .eq("reporter_ip_hash", reporterIpHash)
        .gte("created_at", since);
      if (countErr) throw countErr;
      if ((count || 0) >= MAX_REPORTS_PER_HOUR) {
        return NextResponse.json({ ok: false, error: "Too many reports. Please try again later." }, { status: 429 });
      }
    }

    // Fetch the latest sentiment row for the article (if any).
    const { data: sentimentRow, error: sentErr } = await supabaseAdmin
      .from("bias_analysis")
      .select("sentiment_label,sentiment_score,model_version,created_at")
      .eq("article_id", articleId)
      .eq("model_type", "sentiment")
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();
    if (sentErr) throw sentErr;

    const insertRow = {
      article_id: articleId,
      report_type: reportType,
      predicted_label: sentimentRow?.sentiment_label ?? null,
      predicted_score: sentimentRow?.sentiment_score ?? null,
      predicted_model_version: sentimentRow?.model_version ?? null,
      predicted_created_at: sentimentRow?.created_at ?? null,
      reported_label: reportType === "sentiment" ? reportedLabel : null,
      reported_score: null,
      note,
      context_path: contextPath,
      client_report_id: clientReportId,
      reporter_ip_hash: reporterIpHash,
      user_agent: userAgent,
      status: "new",
    };

    const { error: insErr } = await supabaseAdminUntyped
      .from("sentiment_misclassification_reports")
      .insert(insertRow);

    // Idempotency: if this client_report_id already exists, treat as success.
    const payload = (insErr as unknown as { code?: string } | null) || null;
    if (insErr && payload?.code !== "23505") {
      throw insErr;
    }

    return NextResponse.json({ ok: true });
  } catch (error: unknown) {
    return NextResponse.json(
      { ok: false, error: error instanceof Error ? error.message : "Unknown error" },
      { status: 500 }
    );
  }
}
