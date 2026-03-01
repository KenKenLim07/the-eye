#!/usr/bin/env python3
"""
Beat Monitor - Real-time monitoring of Celery Beat schedule and queue
Shows next scheduled runs, queue status, and recent activity
"""
import redis
import json
import shelve
import os
from datetime import datetime, timedelta
from pathlib import Path

def parse_redis_url(url):
    """Parse Redis URL"""
    if url.startswith("redis://"):
        parts = url.replace("redis://", "").split("/")
        host_port = parts[0].split(":")
        host = host_port[0] if len(host_port) > 0 else "localhost"
        port = int(host_port[1]) if len(host_port) > 1 else 6379
        db = int(parts[1]) if len(parts) > 1 else 0
        return host, port, db
    return None, None, None

def check_beat_schedule_file():
    """Check the beat schedule file for next run times"""
    print("⏰ Beat Schedule (Next Run Times):")
    print("-" * 70)
    
    # Check common locations for beat schedule file
    schedule_paths = [
        "celerybeat-schedule",
        "backend/celerybeat-schedule",
        "/tmp/celerybeat-schedule",
    ]
    
    schedule_found = False
    for schedule_path in schedule_paths:
        if os.path.exists(schedule_path):
            try:
                # Try to read the schedule file
                db = shelve.open(schedule_path, flag='r')
                entries = db.get('entries', {})
                
                if entries:
                    print(f"   📁 Schedule file: {schedule_path}\n")
                    schedule_found = True
                    
                    # Sort by next run time
                    sorted_entries = sorted(
                        entries.items(),
                        key=lambda x: x[1].last_run_at if hasattr(x[1], 'last_run_at') and x[1].last_run_at else datetime.min
                    )
                    
                    for task_name, entry in sorted_entries:
                        if hasattr(entry, 'last_run_at') and entry.last_run_at:
                            last_run = entry.last_run_at
                            if isinstance(last_run, datetime):
                                next_run = last_run + entry.schedule.run_every
                                time_until = next_run - datetime.now()
                                
                                print(f"   📅 {task_name}")
                                print(f"      Last run:  {last_run.strftime('%Y-%m-%d %H:%M:%S')}")
                                print(f"      Next run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                                
                                if time_until.total_seconds() > 0:
                                    hours = int(time_until.total_seconds() // 3600)
                                    minutes = int((time_until.total_seconds() % 3600) // 60)
                                    print(f"      ⏱️  In: {hours}h {minutes}m")
                                else:
                                    print(f"      ⚡ DUE NOW!")
                                print()
                        else:
                            print(f"   📅 {task_name} - Not run yet")
                            print()
                
                db.close()
                break
            except Exception as e:
                print(f"   ⚠️  Could not read schedule file {schedule_path}: {e}")
                continue
    
    if not schedule_found:
        print("   ⚠️  Beat schedule file not found (tasks may not have run yet)")
        print("   💡 Schedule file is created after first task execution")
    print()

def check_redis_queue():
    """Check Redis queue status"""
    try:
        from app.core.config import settings
        
        host, port, db = parse_redis_url(settings.celery_broker_url)
        if not host:
            print("❌ Could not parse Redis URL")
            return
        
        r = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        r.ping()
        
        print("📊 Redis Queue Status:")
        print("-" * 70)
        
        # Check queue length
        queue_length = r.llen("celery")
        print(f"   Tasks waiting in queue: {queue_length}")
        
        if queue_length > 0:
            print(f"\n   📋 Next {min(5, queue_length)} tasks in queue:")
            # Peek at tasks (without removing them)
            tasks = r.lrange("celery", 0, 4)
            for i, task in enumerate(tasks, 1):
                try:
                    task_data = json.loads(task)
                    task_name = task_data.get('task', 'Unknown')
                    print(f"      {i}. {task_name}")
                except:
                    print(f"      {i}. {task[:50]}...")
        else:
            print("   ✅ Queue is empty (all tasks processed)")
        
        print()
        
    except Exception as e:
        print(f"❌ Failed to check Redis queue: {e}\n")

def check_recent_activity():
    """Check recent task activity from result backend"""
    try:
        from app.core.config import settings
        
        host, port, db = parse_redis_url(settings.celery_result_backend)
        if not host:
            return
        
        r = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        
        # Get recent task results
        task_keys = r.keys("celery-task-meta-*")
        
        if task_keys:
            print("📈 Recent Task Activity (Last 5 completed):")
            print("-" * 70)
            
            recent_tasks = []
            for key in task_keys:
                try:
                    task_data = r.get(key)
                    if task_data:
                        task_info = json.loads(task_data)
                        if 'date_done' in task_info and task_info['date_done']:
                            recent_tasks.append((key, task_info))
                except:
                    pass
            
            if recent_tasks:
                recent_tasks.sort(key=lambda x: x[1].get('date_done', ''), reverse=True)
                
                for key, task_info in recent_tasks[:5]:
                    task_id = key.replace("celery-task-meta-", "")[:16]
                    status = task_info.get('status', 'UNKNOWN')
                    date_done = task_info.get('date_done', 'N/A')
                    task_name = task_info.get('task', 'N/A').split('.')[-1]  # Just the task name
                    
                    # Parse date
                    try:
                        if isinstance(date_done, str):
                            dt = datetime.fromisoformat(date_done.replace('Z', '+00:00'))
                            time_ago = datetime.now(dt.tzinfo) - dt
                            ago_str = f"{int(time_ago.total_seconds() // 60)}m ago"
                        else:
                            ago_str = str(date_done)
                    except:
                        ago_str = str(date_done)
                    
                    status_emoji = "✅" if status == "SUCCESS" else "❌" if status == "FAILURE" else "⏳"
                    print(f"   {status_emoji} {task_name}")
                    print(f"      Status: {status} | {ago_str}")
                    print()
            else:
                print("   No completed tasks found\n")
        else:
            print("📈 Recent Task Activity:")
            print("-" * 70)
            print("   No task results found yet\n")
            
    except Exception as e:
        print(f"⚠️  Could not check recent activity: {e}\n")

def show_scheduled_intervals():
    """Show configured intervals from celery_app"""
    try:
        from app.workers.celery_app import celery
        
        print("📋 Configured Task Intervals:")
        print("-" * 70)
        
        if hasattr(celery.conf, 'beat_schedule') and celery.conf.beat_schedule:
            schedules = celery.conf.beat_schedule
            
            for task_name, task_config in schedules.items():
                schedule_obj = task_config.get('schedule')
                if schedule_obj and hasattr(schedule_obj, 'run_every'):
                    interval_seconds = schedule_obj.run_every.total_seconds()
                    interval_hours = interval_seconds / 3600
                    print(f"   • {task_name}: {interval_hours:.2f} hours ({int(interval_seconds)}s)")
        print()
    except Exception as e:
        print(f"⚠️  Could not load schedule config: {e}\n")

def main():
    print("🔍 Celery Beat Monitor")
    print("=" * 70)
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    show_scheduled_intervals()
    check_beat_schedule_file()
    check_redis_queue()
    check_recent_activity()
    
    print("=" * 70)
    print("💡 Quick Commands:")
    print("   • Watch beat logs: docker logs -f ph-eye-beat")
    print("   • Watch worker: docker logs -f ph-eye-worker")
    print("   • Check queue: docker exec ph-eye-redis redis-cli LLEN celery")
    print("   • Monitor Redis: docker exec -it ph-eye-redis redis-cli MONITOR")
    print()

if __name__ == "__main__":
    main()
