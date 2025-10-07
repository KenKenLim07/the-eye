import { supabaseServer } from "@/lib/supabase/server";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils/date";
import Link from "next/link";

export const dynamic = 'force-dynamic';

export default async function FundsPage({ searchParams }: { searchParams?: { page?: string; pageSize?: string } }) {
  const page = Math.max(Number(searchParams?.page || 1), 1);
  const pageSize = Math.min(Math.max(Number(searchParams?.pageSize || 18), 6), 60);
  const from = (page - 1) * pageSize;
  const to = from + pageSize - 1;

  const { data, error, count } = await supabaseServer
    .from("articles")
    .select("*", { count: "exact" })
    .eq("is_funds", true)
    .order("published_at", { ascending: false })
    .range(from, to);

  if (error) {
    return (
      <div className="container mx-auto px-4 py-6">
        <h1 className="text-2xl font-semibold mb-4">Funds-related News</h1>
        <pre className="text-red-600 whitespace-pre-wrap break-words text-sm">{JSON.stringify(error, null, 2)}</pre>
      </div>
    );
  }

  const total = count || 0;
  const totalPages = Math.max(Math.ceil(total / pageSize), 1);

  return (
    <div className="container mx-auto px-4 py-6">
      <h1 className="text-2xl font-semibold mb-4">Funds-related News</h1>
      {!data?.length ? (
        <Card>
          <CardHeader>
            <CardTitle>No funds-related articles</CardTitle>
            <CardDescription>We couldn't find any items marked as funds yet.</CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <>
          <div className="flex items-center justify-between mb-3 text-sm text-muted-foreground">
            <div>
              Page {page} of {totalPages}
            </div>
            <div>
              Total: {total.toLocaleString()} articles
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {data.map((a) => (
              <Card key={a.id}>
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <CardTitle className="line-clamp-2">{a.title}</CardTitle>
                      <CardDescription>
                        {a.source} • {a.category || "Uncategorized"}
                      </CardDescription>
                    </div>
                    <Badge variant="secondary">{formatDate((a.published_at as string | null) ?? null)}</Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground line-clamp-3">{a.content || "No summary available."}</p>
                  {a.url && (
                    <a className="text-sm underline mt-3 inline-block" href={a.url} target="_blank" rel="noreferrer">
                      Read more →
                    </a>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
          <div className="flex items-center justify-between mt-6">
            <Link
              href={`/funds?page=${Math.max(page - 1, 1)}&pageSize=${pageSize}`}
              className={`px-3 py-2 rounded-md text-sm ${page <= 1 ? "pointer-events-none opacity-50" : "underline"}`}
            >
              Previous
            </Link>
            <Link
              href={`/funds?page=${Math.min(page + 1, totalPages)}&pageSize=${pageSize}`}
              className={`px-3 py-2 rounded-md text-sm ${page >= totalPages ? "pointer-events-none opacity-50" : "underline"}`}
            >
              Next
            </Link>
          </div>
        </>
      )}
    </div>
  );
}


