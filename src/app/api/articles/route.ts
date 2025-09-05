import { NextRequest, NextResponse } from "next/server";
import { supabaseServer } from "@/lib/supabase/server";

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const page = Number(searchParams.get("page") || 1);
    const pageSize = Math.min(Number(searchParams.get("pageSize") || 10), 50);
    const source = searchParams.get("source");
    const category = searchParams.get("category");

    const from = (page - 1) * pageSize;
    const to = from + pageSize - 1;

    let query = supabaseServer
      .from("articles")
      .select("*", { count: "exact" })
      .order("published_at", { ascending: false })
      .range(from, to);

    if (source) {
      query = query.eq("source", source);
    }
    if (category) {
      query = query.eq("category", category);
    }

    const { data, error, count } = await query;
    if (error) throw error;

    return NextResponse.json({ ok: true, page, pageSize, count, data });
  } catch (error: unknown) {
    return NextResponse.json({ ok: false, error: error instanceof Error ? error.message : "Unknown error" }, { status: 500 });
  }
}
