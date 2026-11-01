# Monitoring Reference

## Contents
- Health Checks
- Log Management
- Resource Monitoring
- Alerting Patterns
- Backup Verification

## Health Checks

PTVault exposes `/api/health` in `app.py:193-196` — returns `{"status": "ok"}` with no auth required. The Dockerfile and compose file both use Python's `urllib` (not `curl`) since `python:3.11-slim` doesn't include curl.

### Dockerfile Health Check

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1
```

### Check Health Status

```bash
# View current status
docker inspect --format='{{.State.Health.Status}}' ptvault

# View health check history
docker inspect --format='{{json .State.Health}}' ptvault | python3 -m json.tool
```

### WARNING: Health Check Using curl

**The Problem:**

```dockerfile
# BAD - curl not installed in python:3.11-slim
HEALTHCHECK CMD curl -f http://localhost:5000/api/health
```

**Why This Breaks:** `python:3.11-slim` doesn't include curl. The health check silently fails, container reports unhealthy, orchestrators restart it in a loop.

**The Fix:** Use Python's stdlib `urllib.request` as shown above — it's always available.

## Log Management

### View Container Logs

```bash
docker-compose logs -f ptvault      # Follow all logs
docker logs --tail 100 ptvault       # Last 100 lines
docker logs --since 1h ptvault       # Last hour
```

### Log Rotation

```yaml
# docker-compose.yml
services:
  ptvault:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### WARNING: Unbounded Log Growth

**The Problem:**

```yaml
# BAD - No log limits configured
services:
  ptvault:
    build: .
```

**Why This Breaks:**
1. Disk fills up — PTVault logs every request in production
2. System becomes unresponsive
3. Other services may fail when disk is full

**The Fix:** Always set `max-size` and `max-file` in compose. `10m` x `3` files = 30MB max.

## Resource Monitoring

### Container Stats

```bash
# Real-time resource usage
docker stats ptvault

# One-shot (scriptable)
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" ptvault
```

### Monitor Database Size

```bash
# Check database file size
docker exec ptvault ls -lh /app/data/ptvault.db

# Check total data directory (includes uploads)
docker exec ptvault du -sh /app/data/
```

### Simple Monitoring Script

```bash
#!/bin/bash
# monitor.sh — run via cron every 5 minutes

CONTAINER="ptvault"
LOG_FILE="/var/log/ptvault-monitor.log"

# Check if running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "$(date): Container not running!" >> $LOG_FILE
    docker-compose -f /opt/ptvault/docker-compose.yml up -d
fi

# Check health
HEALTH=$(docker inspect --format='{{.State.Health.Status}}' $CONTAINER 2>/dev/null)
if [ "$HEALTH" != "healthy" ]; then
    echo "$(date): Container unhealthy: $HEALTH" >> $LOG_FILE
fi

# Check disk usage (alert at 10GB)
USAGE=$(docker exec $CONTAINER du -s /app/data 2>/dev/null | cut -f1)
if [ "${USAGE:-0}" -gt 10485760 ]; then
    echo "$(date): Data directory exceeds 10GB" >> $LOG_FILE
fi
```

## Alerting Patterns

### Cron-Based Health Check

```bash
# /etc/cron.d/ptvault-monitor
*/5 * * * * root /opt/ptvault/monitor.sh
```

### Webhook Alert on Failure

```bash
#!/bin/bash
# alert.sh

WEBHOOK_URL="https://hooks.slack.com/services/XXX"

if ! curl -sf http://localhost:5000/api/health > /dev/null; then
    curl -X POST -H 'Content-type: application/json' \
        --data '{"text":"PTVault is down!"}' \
        $WEBHOOK_URL
fi
```

## Backup Verification

### Automated Backup Script

```bash
#!/bin/bash
# backup.sh
set -e

BACKUP_DIR="/opt/backups/ptvault"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Stop for consistent backup (WAL checkpoint)
docker-compose -f /opt/ptvault/docker-compose.yml stop

# Backup data directory
tar -czf $BACKUP_DIR/ptvault-$DATE.tar.gz -C /opt/ptvault data/

# Restart
docker-compose -f /opt/ptvault/docker-compose.yml start

# Verify backup contains database
if tar -tzf $BACKUP_DIR/ptvault-$DATE.tar.gz | grep -q "data/ptvault.db"; then
    echo "Backup verified: ptvault-$DATE.tar.gz"
else
    echo "ERROR: Backup verification failed!"
    exit 1
fi

# Cleanup backups older than 7 days
find $BACKUP_DIR -name "ptvault-*.tar.gz" -mtime +7 -delete
```

### Backup Validation

1. Create backup: `./backup.sh`
2. Verify archive: `tar -tzf backup.tar.gz | grep ptvault.db`
3. Test restore to temp location: extract and start a test container against it
4. If restore fails, investigate — repeat until validation passes
5. Only consider backup valid when a test container starts and `/api/health` returns ok

### Backup Cron

```bash
# /etc/cron.d/ptvault-backup
# Daily at 2 AM
0 2 * * * root /opt/ptvault/backup.sh >> /var/log/ptvault-backup.log 2>&1
```
