# CI/CD Reference

## Contents
- Build Pipeline Patterns
- Testing in Containers
- Image Registry Workflow
- Deployment Automation

## Build Pipeline Patterns

### GitHub Actions Workflow

```yaml
name: Build and Test

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest

      - name: Run tests
        run: python -m pytest tests/ -v

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t ptvault:${{ github.sha }} .

      - name: Smoke test container
        run: |
          docker run -d --name test-ptvault -p 5000:5000 ptvault:${{ github.sha }}
          sleep 10
          curl -f http://localhost:5000/api/health || exit 1
          docker stop test-ptvault
```

### WARNING: No Test Stage Before Build

**The Problem:**

```yaml
# BAD - Build and push without testing
jobs:
  build:
    steps:
      - run: docker build -t ptvault .
      - run: docker push registry/ptvault
```

**Why This Breaks:**
1. Broken parser code deployed — tool imports silently fail
2. Migration errors not caught until production startup
3. Auth regressions bypass the **argon2** or **jwt** verification

**The Fix:** Always gate builds on `needs: test`. See the **python** skill for test patterns.

## Testing in Containers

### Integration Test Container

```bash
#!/bin/bash
# test_container.sh
set -e

docker build -t ptvault:test .
docker run -d --name ptvault-test -p 5001:5000 ptvault:test

# Wait for health
for i in $(seq 1 30); do
  if curl -sf http://localhost:5001/api/health > /dev/null; then
    echo "Container healthy"
    break
  fi
  sleep 1
done

# Run API tests against container
python -m pytest tests/ -v -k "not migration"

# Cleanup
docker stop ptvault-test && docker rm ptvault-test
```

### Test with Fixtures

```bash
# Mount test data read-only
docker run -d \
  -v $(pwd)/tests/fixtures:/app/tests/fixtures:ro \
  -e DATABASE_PATH=/app/data/test.db \
  ptvault:test
```

## Image Registry Workflow

### Tag and Push Pattern

```bash
VERSION=$(git describe --tags --always)
docker build -t ptvault:${VERSION} -t ptvault:latest .

docker tag ptvault:${VERSION} registry.example.com/ptvault:${VERSION}
docker push registry.example.com/ptvault:${VERSION}
docker push registry.example.com/ptvault:latest
```

### WARNING: Using :latest in Production

**The Problem:**

```yaml
# BAD - No version pinning
image: ptvault:latest
```

**Why This Breaks:**
1. No rollback capability — you don't know what "latest" was yesterday
2. Unpredictable behavior across deployments
3. Can't reproduce bugs from specific versions

**The Fix:**

```yaml
# GOOD - Pin to git SHA or semver
image: ptvault:abc123f
# Or
image: ptvault:1.2.0
```

## Deployment Automation

### Deploy Script

```bash
#!/bin/bash
# deploy.sh
set -e

VERSION=${1:-latest}
echo "Deploying ptvault:${VERSION}"

# Pull new image
docker pull registry.example.com/ptvault:${VERSION}

# Stop current container
docker-compose down

# Start with new image
IMAGE_TAG=${VERSION} docker-compose up -d

# Verify health
for i in $(seq 1 30); do
  if curl -sf http://localhost:5000/api/health > /dev/null; then
    echo "Deploy successful"
    exit 0
  fi
  sleep 1
done

echo "Deploy failed — health check timeout"
exit 1
```

### Rollback Procedure

```bash
# Tag current as previous before deploying
docker tag ptvault:current ptvault:previous

# If deploy fails
docker-compose down
IMAGE_TAG=previous docker-compose up -d
```

### Build + Deploy Checklist

Copy this checklist for CI/CD setup:
- [ ] Tests pass: `python -m pytest tests/ -v`
- [ ] Build image: `docker build -t ptvault:$(git rev-parse --short HEAD) .`
- [ ] Smoke test: start container, hit `/api/health`
- [ ] Tag image with version
- [ ] Push to registry
- [ ] Deploy to target environment
- [ ] Verify health check passes in production

### Iterate-Until-Pass Pattern

1. Push code changes
2. CI runs tests: `python -m pytest tests/ -v`
3. If tests fail, fix and push again — repeat step 2
4. Once tests pass, CI builds Docker image
5. Smoke test container startup
6. If smoke test fails, check `docker logs` and fix — repeat from step 1
7. Only deploy when both test and smoke stages pass
