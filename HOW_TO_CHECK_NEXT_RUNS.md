# 🔍 How to Check When Tasks Fire Next

## ✅ Your Beat is Working!

Since you confirmed scrapers are firing, here's how to monitor when the **next** ones will run:

## Method 1: Watch Beat Logs (Easiest & Most Reliable)

```powershell
# Watch beat logs in real-time - you'll see when tasks fire
docker logs -f ph-eye-beat
```

**Look for lines like:**
```
Scheduler: Sending due task scrape_rappler (app.workers.tasks.scrape_rappler_task)
Scheduler: Sending due task scrape_gma (app.workers.tasks.scrape_gma_task)
```

These messages appear **exactly when** beat schedules a task. The timestamp shows when it fired.

## Method 2: Check Redis Queue (Real-time)

```powershell
# Check how many tasks are waiting right now
docker exec ph-eye-redis redis-cli LLEN celery

# Watch queue in real-time (see tasks being added as beat fires them)
docker exec -it ph-eye-redis redis-cli MONITOR
```

**What to expect:**
- `0` = Queue empty (all tasks processed)
- `1-10` = Tasks waiting to be processed
- When beat fires a task, you'll see the queue count increase temporarily

## Method 3: Check Beat Schedule File (Next Run Times)

The beat schedule file stores when each task last ran. To see next run times:

```powershell
# Copy the check script into container
docker cp archive/legacy/root_tools/check_next_runs.py ph-eye-beat:/app/backend/

# Run it to see next scheduled times
docker exec ph-eye-beat python /app/backend/check_next_runs.py
```

**Note:** The schedule file is created after tasks run for the first time. If you just started beat, wait for the first tasks to complete.

## Method 4: Quick Status Check Script

```powershell
# Run the quick checker
.\archive\legacy\root_tools\quick_check_beat.ps1
```

This shows:
- Container status
- Queue status  
- Recent activity
- Whether tasks are being scheduled

## Method 5: Calculate Next Run (Manual)

Since you know the intervals, you can calculate:

| Task | Interval | Next Run After Last Execution |
|------|----------|-------------------------------|
| scrape_rappler | 1.0 hour | +1 hour |
| scrape_gma | 1.08 hours | +1h 5m |
| scrape_philstar | 1.17 hours | +1h 10m |
| scrape_inquirer | 1.25 hours | +1h 15m |
| scrape_manila_bulletin | 1.33 hours | +1h 20m |
| scrape_manila_times | 1.42 hours | +1h 25m |
| scrape_sunstar | 1.50 hours | +1h 30m |

**Example:** If `scrape_rappler` ran at 04:25, next run is at 05:25.

## 🎯 Best Practice: Watch in Real-Time

```powershell
# Terminal 1: Watch beat scheduling tasks
docker logs -f ph-eye-beat

# Terminal 2: Watch worker processing tasks  
docker logs -f ph-eye-worker

# Terminal 3: Monitor Redis queue
docker exec -it ph-eye-redis redis-cli MONITOR
```

## 📊 Understanding What You See

### Beat Logs Show:
- ✅ `Scheduler: Sending due task...` = Task is being scheduled NOW
- ✅ `beat: Starting...` = Beat is running
- ❌ No "Sending" messages = Tasks haven't fired yet (wait for interval)

### Worker Logs Show:
- ✅ `Received task: app.workers.tasks.scrape_rappler_task` = Task queued
- ✅ `Task ... succeeded` = Task completed
- ✅ `Scraping completed: X articles` = Scraper finished

### Redis Queue Shows:
- `LLEN celery` = Number of tasks waiting
- `MONITOR` = See every Redis command (tasks being added/removed)

## 💡 Pro Tip

Since your shortest interval is **1 hour** (scrape_rappler), you should see tasks firing approximately every hour. The exact timing depends on when beat started and when each task last ran.

**To verify it's working right now:**
1. Check beat is running: `docker ps | findstr beat`
2. Check recent activity: `docker logs ph-eye-worker --tail 10`
3. Wait and watch: `docker logs -f ph-eye-beat` (you'll see tasks fire within the hour)
# Note (Archived Tools)
The helper scripts referenced here were moved to `archive/legacy/root_tools/` to keep the repo root clean.
If you still need them, use the updated paths below.
