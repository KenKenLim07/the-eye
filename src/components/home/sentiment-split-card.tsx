import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Props = {
  positive: number;
  neutral: number;
  negative: number;
  unlabeled: number;
};

function pct(part: number, total: number): number {
  if (total <= 0) return 0;
  return Math.round((part / total) * 100);
}

export default function SentimentSplitCard({ positive, neutral, negative, unlabeled }: Props) {
  const total = positive + neutral + negative + unlabeled;
  const pPos = pct(positive, total);
  const pNeu = pct(neutral, total);
  const pNeg = pct(negative, total);
  const pUnl = Math.max(0, 100 - pPos - pNeu - pNeg);

  return (
    <Card>
      <CardContent className="p-3 sm:p-4 space-y-2">
        <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Sentiment (visible)</div>
        <div className="u-serif text-2xl sm:text-3xl font-semibold tabular-nums">{total.toLocaleString()}</div>

        <div className="h-2 w-full rounded-full overflow-hidden border bg-muted" aria-label="Sentiment split bar">
          <div className="h-full flex">
            <div className="h-full bg-emerald-600" style={{ width: `${pPos}%` }} aria-label="Positive" />
            <div className="h-full bg-slate-700" style={{ width: `${pNeu}%` }} aria-label="Neutral" />
            <div className="h-full bg-red-600" style={{ width: `${pNeg}%` }} aria-label="Negative" />
            <div className="h-full bg-border" style={{ width: `${pUnl}%` }} aria-label="Unlabeled" />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span className={cn("u-mono text-[10px] uppercase tracking-widest")}>Pos {positive} ({pPos}%)</span>
          <span className={cn("u-mono text-[10px] uppercase tracking-widest")}>Neu {neutral} ({pNeu}%)</span>
          <span className={cn("u-mono text-[10px] uppercase tracking-widest")}>Neg {negative} ({pNeg}%)</span>
          <span className={cn("u-mono text-[10px] uppercase tracking-widest")}>— {unlabeled} ({pUnl}%)</span>
        </div>
      </CardContent>
    </Card>
  );
}

