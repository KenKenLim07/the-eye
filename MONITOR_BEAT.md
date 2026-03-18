# 🔍 How to Monitor Celery Beat

## Quick Status Check

### 1. **Check Next Scheduled Runs** (Most Important!)
```powershell
# Run the monitor script
cd backend
python archive/legacy/root_tools/monitor_beat.py
```

This shows:
- ✅ Next run time for each task
- ⏱️ Time until next run
- 📊 Current queue status
- 📈 Recent task activity

### 2. **Check Redis Queue** (Real-time)
```powershell
# See how many tasks are waiting
docker exec ph-eye-redis redis-cli LLEN celery

# Watch queue in real-time (see tasks being added)
docker exec -it ph-eye-redis redis-cli MONITOR
```

### 3. **Watch Beat Logs** (See when tasks fire)
```powershell
# Follow beat logs in real-time
docker logs -f ph-eye-beat

# Look for lines like:
# "Scheduler: Sending due task scrape_rappler (app.workers.tasks.scrape_rappler_task)"
```

### 4. **Watch Worker Logs** (See tasks executing)
```powershell
# Follow worker logs
docker logs -f ph-eye-worker

# Look for:
# "Received task: app.workers.tasks.scrape_rappler_task"
# "Task app.workers.tasks.scrape_rappler_task succeeded"
```

## Understanding the Schedule

Your tasks run at these intervals:
- **scrape_rappler**: Every **1.0 hour** (3600s)
- **scrape_gma**: Every **1.08 hours** (3888s)
- **scrape_philstar**: Every **1.17 hours** (4212s)
- **scrape_inquirer**: Every **1.25 hours** (4500s)
- **scrape_manila_bulletin**: Every **1.33 hours** (4788s)
- **scrape_manila_times**: Every **1.42 hours** (5112s)
- **scrape_sunstar**: Every **1.50 hours** (5400s)

## What to Look For

### ✅ Beat is Working If:
1. Beat container is running: `docker ps | findstr beat`
2. Beat logs show "Scheduler: Sending due task..." messages
3. Worker logs show "Received task..." messages
4. Queue has tasks (temporarily) when beat fires them

### ❌ Beat is NOT Working If:
1. Beat container keeps restarting
2. No "Sending due task" messages in logs
3. Queue stays empty for hours
4. Worker never receives tasks

## Quick Test Commands

```powershell
# Full status check
.\archive\legacy\root_tools\check_beat.ps1

# Check if beat is scheduling
docker logs ph-eye-beat | findstr "Sending"

# Check queue right now
docker exec ph-eye-redis redis-cli LLEN celery

# See all scheduled tasks and next run times
cd backend && python ../archive/legacy/root_tools/monitor_beat.py
```
# Note (Archived Tools)
This document references older one-off monitoring scripts that have been moved to `archive/legacy/root_tools/`.
For current verification, use `backend/scripts/smoke_test.ps1` and `backend/scripts/pipeline_test.ps1`.
