"use client";

import { useEffect, useMemo, useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetClose, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type Option = { value: string; label: string };

type Props = {
  title?: string;
  source: string;
  period: string;
  sources: ReadonlyArray<Option>;
  periods: ReadonlyArray<Option>;
  disableSource?: boolean;
  disablePeriod?: boolean;
  onApply: (next: { source: string; period: string }) => void;
};

export default function AnalyticsFiltersSheet({
  title = "Filters",
  source,
  period,
  sources,
  periods,
  disableSource = false,
  disablePeriod = false,
  onApply,
}: Props) {
  const [open, setOpen] = useState(false);
  const [draftSource, setDraftSource] = useState(source);
  const [draftPeriod, setDraftPeriod] = useState(period);

  useEffect(() => {
    if (!open) return;
    setDraftSource(source);
    setDraftPeriod(period);
  }, [open, source, period]);

  const canReset = draftSource !== source || draftPeriod !== period;
  const safeSources = useMemo(() => (Array.isArray(sources) && sources.length ? sources : [{ value: "all", label: "All" }]), [sources]);
  const safePeriods = useMemo(() => (Array.isArray(periods) && periods.length ? periods : [{ value: "7d", label: "Last 7 Days" }]), [periods]);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button type="button" variant="outline" className="h-11 gap-2">
          <SlidersHorizontal className="h-4 w-4" />
          Filters
        </Button>
      </SheetTrigger>
      <SheetContent
        side="bottom"
        className="p-4 sm:p-5 rounded-t-xl border-t max-h-[85dvh] overflow-y-auto pb-[max(1rem,env(safe-area-inset-bottom))]"
        showCloseButton
      >
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-border" aria-hidden="true" />
        <SheetHeader className="pb-4">
          <SheetTitle className="u-serif text-lg">{title}</SheetTitle>
        </SheetHeader>

        <div className="grid gap-4">
          <div className="grid gap-2">
            <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Source</div>
            <Select value={draftSource} onValueChange={setDraftSource} disabled={disableSource}>
              <SelectTrigger className="h-11 w-full">
                <SelectValue placeholder="Select source" />
              </SelectTrigger>
              <SelectContent>
                {safeSources.map((s) => (
                  <SelectItem key={s.value} value={s.value}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-2">
            <div className="u-mono text-[10px] uppercase tracking-widest text-muted-foreground">Period</div>
            <Select value={draftPeriod} onValueChange={setDraftPeriod} disabled={disablePeriod}>
              <SelectTrigger className="h-11 w-full">
                <SelectValue placeholder="Select period" />
              </SelectTrigger>
              <SelectContent>
                {safePeriods.map((p) => (
                  <SelectItem key={p.value} value={p.value}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <Button
              type="button"
              variant="outline"
              className="h-11 flex-1"
              disabled={!canReset || (disableSource && disablePeriod)}
              onClick={() => {
                setDraftSource(source);
                setDraftPeriod(period);
              }}
            >
              Reset
            </Button>
            <SheetClose asChild>
              <Button
                type="button"
                className="h-11 flex-1"
                onClick={() => onApply({ source: draftSource, period: draftPeriod })}
              >
                Apply
              </Button>
            </SheetClose>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
