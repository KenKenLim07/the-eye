/**
 * Format date consistently in Asia/Manila timezone for SSR/CSR compatibility
 * Avoids hydration mismatches by using predictable formatting
 */
function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function shiftToManilaUTCFields(date: Date): Date {
  // Manila is fixed UTC+08:00 (no DST). Shift then read with UTC getters.
  return new Date(date.getTime() + 8 * 60 * 60 * 1000);
}

function formatYMDManilaFallback(date: Date): string {
  const shifted = shiftToManilaUTCFields(date);
  const y = shifted.getUTCFullYear();
  const m = pad2(shifted.getUTCMonth() + 1);
  const d = pad2(shifted.getUTCDate());
  return `${y}-${m}-${d}`;
}

function formatHMSManilaFallback(date: Date): string {
  const shifted = shiftToManilaUTCFields(date);
  const hh = pad2(shifted.getUTCHours());
  const mm = pad2(shifted.getUTCMinutes());
  const ss = pad2(shifted.getUTCSeconds());
  return `${hh}:${mm}:${ss}`;
}

function formatInTimeZone(date: Date, timeZone: string, options: Intl.DateTimeFormatOptions): string {
  // Manila is fixed UTC+08:00 with no DST. Prefer a deterministic fallback to avoid
  // device/runtime differences (some environments accept `timeZone` but ignore it).
  if (timeZone === "Asia/Manila" && options.year && options.month && options.day) {
    return formatYMDManilaFallback(date);
  }
  try {
    return new Intl.DateTimeFormat('en-CA', { timeZone, ...options }).format(date);
  } catch {
    // Fallback: keep Manila displays stable even in runtimes without full tz/ICU data.
    if (timeZone === "Asia/Manila" && options.year && options.month && options.day) {
      return formatYMDManilaFallback(date);
    }
    return date.toISOString();
  }
}

function normalizeTimestamp(input: string): string {
  const s = input.trim();

  // If the timestamp string has no explicit timezone (common with `timestamp` columns),
  // treat it as UTC so we can reliably display in Asia/Manila across environments.
  //
  // Example problematic value: "2026-03-24T03:38:49" (no "Z" / "+00:00")
  // If parsed as local time in Manila, it will appear 8 hours behind.
  const hasExplicitTz = /(Z|[+-]\d{2}:\d{2})$/.test(s);
  if (hasExplicitTz) return s;

  // Handle "YYYY-MM-DD HH:mm:ss(.sss)" and "YYYY-MM-DDTHH:mm:ss(.sss)"
  const naiveDateTime = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(s);
  if (naiveDateTime) return s.replace(" ", "T") + "Z";

  // Handle date-only strings.
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(s);
  if (dateOnly) return `${s}T00:00:00Z`;

  return s;
}

function toDateSafe(input: string | null): Date | null {
  if (!input) return null;
  const d = new Date(normalizeTimestamp(input));
  return isNaN(d.getTime()) ? null : d;
}

export function formatDate(dateString: string | null): string {
  const date = toDateSafe(dateString);
  if (!date) return "Unknown";
  // en-CA + timeZone=Asia/Manila yields YYYY-MM-DD
  return formatInTimeZone(date, 'Asia/Manila', { year: 'numeric', month: '2-digit', day: '2-digit' });
}

/**
 * Format date with time (YYYY-MM-DD HH:mm:ss) in Asia/Manila
 */
export function formatDateTime(dateString: string | null): string {
  const date = toDateSafe(dateString);
  if (!date) return "Unknown";

  const ymd = formatInTimeZone(date, "Asia/Manila", { year: "numeric", month: "2-digit", day: "2-digit" });
  // Deterministic Manila clock: avoids mobile/desktop discrepancies.
  return `${ymd} ${formatHMSManilaFallback(date)}`;
}

export function toMillis(dateString: string | null): number {
  const date = toDateSafe(dateString);
  return date ? date.getTime() : 0;
}

/**
 * Format relative time (e.g., "2 hours ago")
 * This should only be used on client-side to avoid hydration issues
 */
export function formatRelativeTime(dateString: string | null): string {
  const date = toDateSafe(dateString);
  if (!date) return "Unknown";

  try {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays > 0) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    if (diffHours > 0) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    return "Just now";
  } catch {
    return "Unknown";
  }
}
