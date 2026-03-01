#!/usr/bin/env python3
"""
Check Next Scheduled Runs - Run this inside the Docker container
Usage: docker exec ph-eye-beat python /app/backend/check_next_runs.py
"""
import shelve
import os
from datetime import datetime

def check_next_runs():
    schedule_path = "/app/backend/celerybeat-schedule.db"
    
    if not os.path.exists(schedule_path):
        print("⚠️  Beat schedule file not found yet")
        print("   Tasks will create the schedule file on first run")
        return
    
    try:
        db = shelve.open(schedule_path.replace('.db', ''), flag='r')
        entries = db.get('entries', {})
        
        if not entries:
            print("⚠️  No scheduled entries found in schedule file")
            db.close()
            return
        
        print("⏰ Next Scheduled Runs:")
        print("=" * 70)
        print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Sort by next run time
        tasks_with_times = []
        for task_name, entry in entries.items():
            if hasattr(entry, 'last_run_at') and entry.last_run_at:
                last_run = entry.last_run_at
                if isinstance(last_run, datetime):
                    next_run = last_run + entry.schedule.run_every
                    time_until = next_run - datetime.now()
                    tasks_with_times.append((task_name, last_run, next_run, time_until))
        
        if not tasks_with_times:
            print("⚠️  No tasks have run yet - schedule will be created on first execution")
            db.close()
            return
        
        # Sort by next run time
        tasks_with_times.sort(key=lambda x: x[2])
        
        for task_name, last_run, next_run, time_until in tasks_with_times:
            print(f"📅 {task_name}")
            print(f"   Last run:  {last_run.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Next run:  {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            
            if time_until.total_seconds() > 0:
                hours = int(time_until.total_seconds() // 3600)
                minutes = int((time_until.total_seconds() % 3600) // 60)
                seconds = int(time_until.total_seconds() % 60)
                print(f"   ⏱️  In: {hours}h {minutes}m {seconds}s")
            else:
                print(f"   ⚡ DUE NOW!")
            print()
        
        db.close()
        
    except Exception as e:
        print(f"❌ Error reading schedule: {e}")

if __name__ == "__main__":
    check_next_runs()
