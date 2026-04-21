# Remove Fixed Date-Range Filters (Start/End Dates) — Post-Documentation Cleanup

This repo currently supports **fixed PH-local date windows** for analytics pages (Correlation/Trends/Entities) via `start_local`/`end_local` query params and UI date inputs. This was added to **freeze dashboard windows for thesis screenshots** (e.g., `2026-03-25 → 2026-03-31`).

When you’re done documenting, follow this checklist to **remove the feature cleanly** and return to the original **rolling period windows** (`7d` / `30d`, `include_today`).

## Quick search (what you’re removing)

Run:

```bash
grep -RIn "start_local\\|end_local\\|window_start_local\\|window_end_local\\|custom_range" backend src
```

## 1) Backend removal (FastAPI)

### A) Remove custom-window helper + params

File: `backend/app/api/ml_router.py`

1. Delete the custom window code:
   - `ANALYTICS_MAX_WINDOW_DAYS`
   - `_compute_ph_window_bounds(...)`
2. Remove `start_local` and `end_local` query params from:
   - `GET /ml/correlation`
   - `GET /ml/trends`
   - `GET /ml/entities/top`
3. Restore window calculation to use only:
   - `period` (`7d|30d`)
   - `include_today` (`true|false`)
4. Remove any custom-window metadata fields from responses:
   - `custom_range`
   - `window_start_local`
   - `window_end_local`
5. Simplify cache keys:
   - remove any `custom:` tags and date-range components from cache keys.

### B) (Optional) Keep or revert CORS env support

The fixed-date feature added env-driven CORS so Vercel can call FastAPI.

File: `backend/app/main.py`

- If you still want Vercel → FastAPI calls for *any* live analytics, **keep** `CORS_ALLOW_ORIGINS`.
- If you want to revert to localhost-only CORS, replace `cors_allow_origins()` usage with the original static `allow_origins=[...]`.

## 2) Frontend removal (Next.js)

### A) Remove date inputs from shared filter sheet

File: `src/components/analytics/analytics-filters-sheet.tsx`

1. Remove:
   - `startDate` / `endDate` props
   - `<Input type="date" ... />` fields
   - range validation (`MAX_WINDOW_DAYS`, `rangeError`, etc.)
2. Restore `onApply` signature to only pass `{ source, period }`.

### B) Remove page-level state + requests

Files:
- `src/app/correlation/page.tsx`
- `src/app/trends/page.tsx`
- `src/app/entities/page.tsx`

In each page:
1. Remove state:
   - `startDate`, `endDate`
   - `hasCustomRange`, `customRangeNeedsBackend`
2. Remove:
   - “Window: … (PH)” header line
   - the destructive `<Alert>` about needing a backend
   - ActiveFilters badges for `start` / `end`
3. Restore fetchers to:
   - use snapshots when configured/unavailable backend
   - call backend endpoints with only `period/include_today` (no `start_local/end_local`)

## 3) README + env cleanup (recommended)

If you referenced custom date windows in docs, remove those notes:
- `README.md`

Then remove any no-longer-needed env vars from deployment:
- Vercel: `NEXT_PUBLIC_BACKEND_URL` (only if you don’t need live backend calls anymore)
- Backend: `CORS_ALLOW_ORIGINS` (only if you reverted CORS to static localhost)

## 4) Verification checklist

1. UI: Filters only show **Source** + **Period** (no dates).
2. Correlation/Trends/Entities work in:
   - local dev (`npm run dev`) with backend running
   - snapshot mode (if you use it) without any date picker behavior
3. Backend endpoints no longer accept custom ranges:
   - `/ml/correlation?start_local=...&end_local=...` should either 400 or ignore (depending on how you revert).

