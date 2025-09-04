import { NextResponse } from "next/server";
import { supabaseServer } from "@/lib/supabase/server";

export async function POST() {
  try {
    // Current schema uses string source/category in articles, so seed only articles
    const now = new Date();
    const articles = [
      {
        source: "ABS-CBN News",
        category: "Politics",
        title: "Senate to probe proposed policy changes",
        url: "https://news.abs-cbn.com/mocked-1",
        content: "This is a mock article about policy changes in the senate...",
        published_at: now.toISOString(),
      },
      {
        source: "GMA News Online",
        category: "Business",
        title: "Peso gains as markets rally",
        url: "https://www.gmanetwork.com/news/mocked-2",
        content: "Market rally leads to peso gains against the dollar...",
        published_at: now.toISOString(),
      },
      {
        source: "Philippine Star",
        category: "Sports",
        title: "Gilas secures close win in qualifiers",
        url: "https://www.philstar.com/mocked-3",
        content: "Gilas Pilipinas secures a thrilling victory...",
        published_at: now.toISOString(),
      },
    ];

    // Avoid duplicates by checking existing URLs
    const urls = articles.map((a) => a.url).filter(Boolean) as string[];
    const { data: existingArticles, error: existingArticlesErr } = await supabaseServer
      .from("articles")
      .select("id,url")
      .in("url", urls);
    if (existingArticlesErr) throw existingArticlesErr;

    const existingUrls = new Set(existingArticles?.map((a) => a.url).filter(Boolean) as string[]);
    const articlesToInsert = articles.filter((a) => a.url && !existingUrls.has(a.url));

    if (articlesToInsert.length > 0) {
      const { error: insertArticlesErr } = await supabaseServer
        .from("articles")
        .insert(articlesToInsert);
      if (insertArticlesErr) throw insertArticlesErr;
    }

    return NextResponse.json({ ok: true, inserted: articlesToInsert.length });
  } catch (error: any) {
    return NextResponse.json({ ok: false, error: { message: error.message, details: error?.details, code: error?.code, hint: error?.hint } }, { status: 500 });
  }
} 