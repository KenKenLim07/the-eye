/**
 * Format date consistently for SSR/CSR compatibility
 * Avoids hydration mismatches by using predictable formatting
 */
export function formatDate(dateString: string | null): string {
  if (!dateString) return "Unknown";
  
  try {
    const date = new Date(dateString);
    // Use ISO date format (YYYY-MM-DD) for consistency
    return date.toISOString().split('T')[0];
  } catch {
    return "Unknown";
  }
}

/**
 * Format date with time for more detailed display
 */
export function formatDateTime(dateString: string | null): string {
  if (!dateString) return "Unknown";
  
  try {
    const date = new Date(dateString);
    // Use ISO format for consistency
    return date.toISOString().replace('T', ' ').split('.')[0];
  } catch {
    return "Unknown";
  }
}

/**
 * Format relative time (e.g., "2 hours ago")
 * This should only be used on client-side to avoid hydration issues
 */
export function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return "Unknown";
  
  try {
    const date = new Date(dateString);
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
