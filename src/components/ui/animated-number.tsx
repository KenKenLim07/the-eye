"use client";

import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";

type Props = {
  value: number;
  start?: number;
  durationMs?: number;
  animate: boolean;
  format?: (n: number) => string;
  className?: string;
};

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

export default function AnimatedNumber({
  value,
  start = 0,
  durationMs = 700,
  animate,
  format,
  className,
}: Props) {
  const fmt = useMemo(() => format ?? ((n: number) => n.toLocaleString()), [format]);

  // Match SSR output (final value), then switch to an animated count-up before first paint when needed.
  const [display, setDisplay] = useState<number>(value);
  const rafRef = useRef<number | null>(null);

  useLayoutEffect(() => {
    // Always cancel any in-flight animation on prop changes.
    if (rafRef.current != null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }

    if (!animate) {
      setDisplay(value);
      return;
    }

    const from = Number.isFinite(start) ? start : 0;
    const to = Number.isFinite(value) ? value : 0;
    const dur = Math.max(120, Number.isFinite(durationMs) ? durationMs : 700);
    const t0 = performance.now();

    setDisplay(from);

    const tick = (t: number) => {
      const p = Math.min(1, Math.max(0, (t - t0) / dur));
      const eased = easeOutCubic(p);
      const next = from + (to - from) * eased;
      setDisplay(Math.round(next));
      if (p < 1) rafRef.current = requestAnimationFrame(tick);
      else rafRef.current = null;
    };

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [animate, durationMs, start, value]);

  return (
    <span className={cn("tabular-nums inline-block", className)} aria-label={fmt(value)}>
      {fmt(display)}
    </span>
  );
}

