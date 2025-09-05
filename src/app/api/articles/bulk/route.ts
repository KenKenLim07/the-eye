import { NextRequest, NextResponse } from "next/server";
import { supabaseServer } from "@/lib/supabase/server";

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const limit = Math.min(Number(searchParams.get("limit") || 20), 50);
    
    // Define all news sources
    const sources = [
      "GMA",
      "Rappler", 
      "Inquirer",
      "Philstar",
      "Sunstar",
      "Manila Bulletin"
    ];

    // Create parallel queries for all sources
    const queries = sources.map(source => 
      supabaseServer
        .from("articles")
        .select("*")
        .eq("source", source)
        .order("published_at", { ascending: false })
        .limit(limit)
    );

    // Execute all queries in parallel
    const results = await Promise.all(queries);
    
    // Process results and handle errors
    const articlesBySource: Record<string, any[]> = {};
    const errors: string[] = [];

    results.forEach((result, index) => {
      const source = sources[index];
      if (result.error) {
        errors.push(`${source}: ${result.error.message}`);
        articlesBySource[source] = [];
      } else {
        articlesBySource[source] = result.data || [];
      }
    });

    return NextResponse.json({ 
      ok: true, 
      data: articlesBySource,
      errors: errors.length > 0 ? errors : undefined,
      timestamp: new Date().toISOString()
    });
  } catch (error: unknown) {
    return NextResponse.json({ 
      ok: false, 
      error: error instanceof Error ? error.message : "Unknown error" 
    }, { status: 500 });
  }
}
