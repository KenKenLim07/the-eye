#!/usr/bin/env python3
"""
Check Next Scheduled Runs - run inside beat container:
  docker exec ph-eye-beat python /app/check_next_runs.py
"""
import glob
import os
import shelve
from datetime import datetime


def _candidate_schedule_bases() -> list[str]:
    bases = []
    for path in (
        "/app/backend/celerybeat-schedule",
        "/app/backend/celerybeat-schedule.db",
        "/app/celerybeat-schedule",
        "/app/celerybeat-schedule.db",
        "celerybeat-schedule",
        "celerybeat-schedule.db",
    ):
        if os.path.exists(path):
            bases.append(path.replace(".db", ""))
    # Deduplicate while preserving order
    out = []
    seen = set()
    for b in bases:
        if b not in seen:
            seen.add(b)
            out.append(b)
    return out


def _open_schedule_db():
    for base in _candidate_schedule_bases():
        try:
            db = shelve.open(base, flag="r")
            return base, db
        except Exception:
            continue
    return None, None


def check_next_runs() -> int:
    print("Beat schedule files found:")
    for f in sorted(glob.glob("/app/backend/celerybeat-schedule*") + glob.glob("/app/celerybeat-schedule*")):
        print(f"  - {f}")

    base, db = _open_schedule_db()
    if db is None:
        print("\nERROR: no readable beat schedule database found.")
        return 1

    print(f"\nUsing schedule DB base: {base}")
    try:
        keys = list(db.keys())
        print(f"DB keys: {keys}")
        entries = db.get("entries", {})
        print(f"entries count: {len(entries)}")

        if not entries:
            print("WARNING: no scheduled entries found in beat DB.")
            return 2

        now = datetime.now()
        print("\nNext Scheduled Runs:")
        print("=" * 70)
        print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")

        rows = []
        for task_name, entry in entries.items():
            last_run = getattr(entry, "last_run_at", None)
            sched = getattr(entry, "schedule", None)
            run_every = getattr(sched, "run_every", None)
            if last_run and run_every:
                next_run = last_run + run_every
                rows.append((str(task_name), last_run, next_run, next_run - now))

        if not rows:
            print("WARNING: entries exist but no run metadata yet.")
            return 3

        rows.sort(key=lambda r: r[2])
        for task_name, last_run, next_run, delta in rows:
            print(f"- {task_name}")
            print(f"  last: {last_run}")
            print(f"  next: {next_run}")
            secs = int(delta.total_seconds())
            if secs >= 0:
                h, rem = divmod(secs, 3600)
                m, s = divmod(rem, 60)
                print(f"  in:   {h}h {m}m {s}s")
            else:
                print("  in:   DUE NOW")
            print()
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(check_next_runs())
