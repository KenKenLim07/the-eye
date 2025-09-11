/**
 * Format date consistently in Asia/Manila timezone for SSR/CSR compatibility
 * Avoids hydration mismatches by using predictable formatting
 */
function formatInTimeZone(date: Date, timeZone: string, options: Intl.DateTimeFormatOptions): string {
  try {
    return new Intl.DateTimeFormat('en-CA', { timeZone, ...options }).format(date);
  } catch {
    // Fallback: ISO in UTC if Intl fails
    return date.toISOString();
  }
}

function toDateSafe(input: string | null): Date | null {
  if (!input) return null;
  const d = new Date(input);
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

  // We need YYYY-MM-DD and HH:mm:ss separately in Manila TZ
  const ymd = formatInTimeZone(date, 'Asia/Manila', { year: 'numeric', month: '2-digit', day: '2-digit' });
  const timeParts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Manila',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).formatToParts(date);
  const hh = timeParts.find(p => p.type === 'hour')?.value ?? '00';
  const mm = timeParts.find(p => p.type === 'minute')?.value ?? '00';
  const ss = timeParts.find(p => p.type === 'second')?.value ?? '00';
  return `${ymd} ${hh}:${mm}:${ss}`;
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
