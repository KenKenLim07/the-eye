# 🔧 Fix DNS Resolution Issue on Windows Docker

## Problem
Worker container can't resolve hostnames (DNS failure):
```
[Errno -3] Temporary failure in name resolution
```

This prevents connecting to Supabase and other external services.

## Solutions (Try in Order)

### Solution 1: Restart Docker Desktop (Most Common Fix)
1. Right-click Docker Desktop icon in system tray
2. Click "Restart"
3. Wait for Docker to fully restart
4. Run: `docker-compose up -d`

This fixes DNS issues 90% of the time on Windows.

### Solution 2: Reset Docker Network
```powershell
# Stop all containers
docker-compose down

# Remove all networks
docker network prune -f

# Restart Docker Desktop (manually)
# Then start containers again
docker-compose up -d
```

### Solution 3: Check Windows DNS Settings
1. Open Network Settings
2. Check if you're using a VPN (disable temporarily)
3. Ensure Windows DNS is working: `nslookup google.com`
4. If Windows DNS fails, fix your network connection first

### Solution 4: Use Host Network (Last Resort)
If DNS still fails, you can try using host network mode (not recommended for production):

```yaml
worker:
  network_mode: host
  # Remove dns: section when using host network
```

**Warning:** This exposes containers directly to host network.

### Solution 5: Check Docker Desktop Settings
1. Open Docker Desktop
2. Go to Settings → Resources → Network
3. Ensure "Enable host networking" is OFF (unless using Solution 4)
4. Restart Docker Desktop

## Verify Fix
After applying a solution, test DNS:
```powershell
docker exec ph-eye-worker python -c "import socket; print(socket.gethostbyname('google.com'))"
```

Should output an IP address (not an error).

## If Still Failing
1. Check Windows Firewall isn't blocking Docker
2. Disable VPN temporarily
3. Check if corporate network has DNS restrictions
4. Try using mobile hotspot to test if it's network-related
