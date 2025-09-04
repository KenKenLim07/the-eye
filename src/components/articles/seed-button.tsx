"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

export default function SeedButton() {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function onSeed() {
    setLoading(true);
    setMessage(null);
    try {
      const res = await fetch("/api/seed", { method: "POST" });
      const json = await res.json();
      if (!res.ok || !json.ok) {
        const errText = JSON.stringify(json.error ?? json, null, 2);
        throw new Error(errText);
      }
      const count = typeof json.inserted === "number" ? json.inserted : undefined;
      setMessage(count !== undefined ? `Seeded ${count} article(s). Refreshing...` : "Mock data seeded. Refreshing...");
      setTimeout(() => window.location.reload(), 600);
    } catch (e: any) {
      const text = typeof e?.message === "string" ? e.message : JSON.stringify(e, null, 2);
      setMessage(text);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-center gap-2 justify-center">
      <Button onClick={onSeed} disabled={loading}>
        {loading ? "Seeding..." : "Seed Mock Data"}
      </Button>
      {message && (
        <pre className="text-xs text-muted-foreground whitespace-pre-wrap break-words max-w-full">{message}</pre>
      )}
    </div>
  );
} 