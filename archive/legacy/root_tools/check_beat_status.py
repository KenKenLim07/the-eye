#!/usr/bin/env python3
"""
Beat Status Checker - Verify Celery Beat is working correctly
Shows scheduled tasks, next run times, and Redis queue status
"""
import redis
import json
from datetime import datetime, timedelta
from app.core.config import settings

def check_beat_status():
    """Check Celery Beat status and scheduled tasks"""
    print("🔍 Celery Beat Status Checker")
    print("=" * 60)
    
    # Connect to Redis
    try:
        broker_url = settings.celery_broker_url
        if broker_url.startswith("redis://"):
            # Parse redis://host:port/db
            parts = broker_url.replace("redis://", "").split("/")
            host_port = parts[0].split(":")
            host = host_port[0] if len(host_port) > 0 else "localhost"
            port = int(host_port[1]) if len(host_port) > 1 else 6379
            db = int(parts[1]) if len(parts) > 1 else 0
            
            r = redis.Redis(host=host, port=port, db=db, decode_responses=True)
            r.ping()
            print(f"✅ Connected to Redis: {host}:{port}/{db}\n")
        else:
            print(f"❌ Unsupported broker URL: {broker_url}")
            return
    except Exception as e:
        print(f"❌ Failed to connect to Redis: {e}")
        print(f"   Broker URL: {broker_url}")
        return
    
    # Check Redis queue status
    print("📊 Redis Queue Status:")
    print("-" * 60)
    
    # Get queue length (default queue)
    queue_length = r.llen("celery")
    print(f"   Tasks in queue: {queue_length}")
    
    # Get all keys related to celery
    all_keys = r.keys("celery*")
    print(f"   Celery-related keys: {len(all_keys)}")
    
    # Check for beat schedule
    beat_schedule_key = "celerybeat-schedule"
    if r.exists(beat_schedule_key):
        print(f"   ✅ Beat schedule file exists")
        # Try to get schedule info
        try:
            schedule_data = r.get(beat_schedule_key)
            if schedule_data:
                print(f"   Schedule data size: {len(schedule_data)} bytes")
        except:
            pass
    else:
        print(f"   ⚠️  Beat schedule file not found (may be using file-based storage)")
    
    print()
    
    # Check scheduled tasks from celery_app
    print("⏰ Scheduled Tasks (from celery_app.py):")
    print("-" * 60)
    
    from app.workers.celery_app import celery
    
    if hasattr(celery.conf, 'beat_schedule') and celery.conf.beat_schedule:
        schedules = celery.conf.beat_schedule
        print(f"   Total scheduled tasks: {len(schedules)}\n")
        
        for task_name, task_config in schedules.items():
            schedule_obj = task_config.get('schedule')
            task_path = task_config.get('task', 'N/A')
            
            if schedule_obj:
                # Get interval in seconds
                if hasattr(schedule_obj, 'run_every'):
                    interval_seconds = schedule_obj.run_every.total_seconds()
                    interval_hours = interval_seconds / 3600
                    next_run_estimate = datetime.now() + timedelta(seconds=interval_seconds)
                    
                    print(f"   📅 {task_name}")
                    print(f"      Task: {task_path}")
                    print(f"      Interval: {interval_hours:.2f} hours ({interval_seconds}s)")
                    print(f"      Next run (est): {next_run_estimate.strftime('%Y-%m-%d %H:%M:%S')}")
                    print()
    else:
        print("   ⚠️  No beat schedule found in celery configuration")
    
    # Check for recent task results
    print("📈 Recent Task Activity:")
    print("-" * 60)
    
    result_backend = settings.celery_result_backend
    if result_backend.startswith("redis://"):
        parts = result_backend.replace("redis://", "").split("/")
        host_port = parts[0].split(":")
        result_host = host_port[0] if len(host_port) > 0 else "localhost"
        result_port = int(host_port[1]) if len(host_port) > 1 else 6379
        result_db = int(parts[1]) if len(parts) > 1 else 1
        
        result_r = redis.Redis(host=result_host, port=result_port, db=result_db, decode_responses=True)
        
        # Get task result keys
        task_keys = result_r.keys("celery-task-meta-*")
        print(f"   Total task results: {len(task_keys)}")
        
        if task_keys:
            # Get most recent tasks
            recent_tasks = []
            for key in task_keys[:10]:  # Check first 10
                try:
                    task_data = result_r.get(key)
                    if task_data:
                        task_info = json.loads(task_data)
                        if 'date_done' in task_info:
                            recent_tasks.append((key, task_info))
                except:
                    pass
            
            if recent_tasks:
                recent_tasks.sort(key=lambda x: x[1].get('date_done', ''), reverse=True)
                print(f"\n   Most recent tasks:")
                for key, task_info in recent_tasks[:5]:
                    task_id = key.replace("celery-task-meta-", "")
                    status = task_info.get('status', 'UNKNOWN')
                    date_done = task_info.get('date_done', 'N/A')
                    task_name = task_info.get('task', 'N/A')
                    print(f"      • {task_name[:40]}")
                    print(f"        ID: {task_id[:20]}... Status: {status}")
                    print(f"        Done: {date_done}")
                    print()
    
    print("=" * 60)
    print("💡 Tips:")
    print("   • Check beat logs: docker logs ph-eye-beat")
    print("   • Check worker logs: docker logs ph-eye-worker")
    print("   • Monitor queue: docker exec -it ph-eye-redis redis-cli LLEN celery")
    print("   • Watch beat in real-time: docker logs -f ph-eye-beat")

if __name__ == "__main__":
    check_beat_status()
