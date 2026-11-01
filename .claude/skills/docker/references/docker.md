# Docker Patterns Reference

## Contents
- Dockerfile Structure
- Docker Compose Configuration
- Volume Management
- Layer Caching
- Security Hardening
- Common Errors

## Dockerfile Structure

PTVault's `Dockerfile` uses `python:3.11-slim` with system deps for C extensions (argon2-cffi, PyNaCl):

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    gcc libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data /app/data/uploads

EXPOSE 5000
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/app/data/ptvault.db
ENV ENVIRONMENT=production

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

CMD ["python", "app.py"]
```

### WARNING: Missing Multi-Stage Build

**The Problem:** `gcc` and `libssl-dev` ship in the final image (~200MB overhead). Build tools are only needed to compile C extensions.

**The Fix:**

```dockerfile
FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y gcc libssl-dev
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim
COPY --from=builder /install /usr/local
WORKDIR /app
COPY . .
RUN mkdir -p /app/data /app/data/uploads
EXPOSE 5000
CMD ["python", "app.py"]
```

**Why:** Production images should contain only runtime dependencies. Shipping compilers creates unnecessary attack surface and bloat.

### WARNING: Fat Images from Dev Dependencies

**The Problem:**

```dockerfile
# BAD - Copies everything including .git, tests, planning docs
COPY . .
```

**The Fix:** The `.dockerignore` already excludes `data/`, `tests/`, `.git/`, `*.md`, `.planning/`. Verify it stays up-to-date when adding directories. Alternatively, use explicit `COPY` for each directory:

```dockerfile
COPY app.py config.py features.py ./
COPY models/ ./models/
COPY routes/ ./routes/
COPY middleware/ ./middleware/
COPY utils/ ./utils/
COPY templates/ ./templates/
COPY static/ ./static/
```

## Docker Compose Configuration

```yaml
version: '3.8'
services:
  ptvault:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ptvault
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data          # Database + uploads persist here
      - ./.env:/app/.env:ro       # Config read-only
    environment:
      - FLASK_APP=app.py
      - PYTHONUNBUFFERED=1
      - DATABASE_PATH=/app/data/ptvault.db
      - ENVIRONMENT=production
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s
    networks:
      - ptvault-network

networks:
  ptvault-network:
    driver: bridge
```

### WARNING: Missing Volume Persistence

```yaml
# BAD - No volume mount, data lost on container restart
services:
  ptvault:
    build: .
    ports:
      - "5000:5000"
```

ALWAYS mount `./data:/app/data`. SQLite creates `-wal` and `-shm` sidecar files — the entire `data/` directory must be mounted, not just the `.db` file.

See the **sqlite** skill for WAL mode details.

## Volume Management

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `./data` | `/app/data` | SQLite DB, uploads, atomics cache |
| `./.env` | `/app/.env:ro` | Secrets (read-only mount) |

### Backup Patterns

```bash
# Live backup (safe — SQLite handles locking)
docker cp ptvault:/app/data/ptvault.db ./backup-$(date +%Y%m%d).db

# Full data backup including uploads and atomics
docker cp ptvault:/app/data ./data-backup-$(date +%Y%m%d)
```

## Layer Caching

```dockerfile
# GOOD - Dependencies cached separately from code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
```

```dockerfile
# BAD - Every code change invalidates pip install cache
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
```

## Security Hardening

### WARNING: Running as Root

The current Dockerfile runs as root. A container escape exploit grants root on the host.

```dockerfile
# Add before CMD
RUN useradd -r -s /bin/false ptvault && \
    chown -R ptvault:ptvault /app/data
USER ptvault
CMD ["python", "app.py"]
```

### Read-Only Filesystem

```yaml
services:
  ptvault:
    read_only: true
    security_opt:
      - no-new-privileges:true
    tmpfs:
      - /tmp
    volumes:
      - ./data:/app/data
```

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `bind: address already in use` | Port 5000 taken | Use `-p 8080:5000` |
| `Permission denied` on data volume | Host dir ownership | `sudo chown -R 1000:1000 ./data` |
| Container exits immediately | Missing .env or bad config | `docker logs ptvault` to diagnose |
| `database is locked` | Concurrent writes | Ensure single container per DB; see **sqlite** skill |

## Deployment Checklist

Copy this checklist for Docker deployments:
- [ ] Copy `.env.example` to `.env` with real `SECRET_KEY` and `JWT_SECRET_KEY`
- [ ] Create `./data` directory with correct permissions
- [ ] Build image: `docker-compose build`
- [ ] Start container: `docker-compose up -d`
- [ ] Verify health: `curl http://localhost:5000/api/health`
- [ ] Check logs: `docker-compose logs -f`
- [ ] Test login at `http://localhost:5000`
