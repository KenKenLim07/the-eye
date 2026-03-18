# 🚀 PH Eye Service Management

## Quick Commands

### Start Services
```bash
./start_ph_eye.sh
```
- Starts FastAPI server, Celery worker, and Celery beat
- Services run in background (survive VS Code closure)
- Logs saved to `backend/api.log`, `backend/worker.log`, `backend/beat.log`

### Stop Services  
```bash
./stop_ph_eye.sh
```
- Stops all PH Eye services
- Clean shutdown

### Check Status
```bash
./archive/legacy/root_tools/check_ph_eye.sh
```
- Shows if all services are running
- Displays recent VADER analysis count
- Shows log file locations

## What Happens When You...

### Close VS Code
- ✅ **Services keep running** (if started with `./start_ph_eye.sh`)
- ✅ **New articles still scraped**
- ✅ **VADER analysis continues**
- ✅ **API remains accessible**

### Close MacBook Lid
- ✅ **Services keep running** (if started with `./start_ph_eye.sh`)
- ✅ **Background processes continue**
- ✅ **System stays active**

### Restart Mac
- ❌ **All services stop**
- ❌ **Need to run `./start_ph_eye.sh` again**
- ❌ **No automatic restart**

### Empty Battery
- ❌ **All services stop**
- ❌ **Need to run `./start_ph_eye.sh` again**
- ❌ **No automatic restart**

## Production Solutions

### Option 1: Cloud Deployment (Recommended)
Deploy to **Railway**, **Render**, or **DigitalOcean**:
- ✅ **24/7 uptime**
- ✅ **Auto-restart on failure**
- ✅ **No dependency on your Mac**
- ✅ **Professional hosting**

### Option 2: Docker (Local Production)
```bash
# Create docker-compose.yml for local production
# Services auto-restart and persist across reboots
```

### Option 3: macOS LaunchAgent (Advanced)
Create system service that auto-starts on boot:
```bash
# Create ~/Library/LaunchAgents/com.ph-eye.services.plist
# Auto-starts services on Mac boot
```

## Current Status
- **FastAPI**: http://localhost:8000
- **Trends API**: http://localhost:8000/ml/trends
- **Health Check**: http://localhost:8000/health
- **Logs**: `backend/*.log`

## Troubleshooting

### Services Not Starting
```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill existing processes
./stop_ph_eye.sh

# Check logs
tail -f backend/api.log
tail -f backend/worker.log
tail -f backend/beat.log
```

### VADER Not Working
```bash
# Check Celery worker
./archive/legacy/root_tools/check_ph_eye.sh

# Manual analysis test
curl -X POST http://localhost:8000/ml/analyze \
  -H "Content-Type: application/json" \
  -d '{"since":"2025-01-01T00:00:00Z"}'
```
# Note (Archived Tools)
Some legacy helper scripts referenced in this document were moved to `archive/legacy/root_tools/` to keep the repo root clean.
Primary workflow is now documented in `README.md` (Docker Compose + smoke/pipeline tests).
