# PTVault Docker Image
# Production-ready containerized deployment

# Pinned by digest (L-5): a tag can be repointed, a digest cannot. To update,
# look up the current digest of the tag and change both together:
#   docker buildx imagetools inspect python:3.11-slim
FROM python:3.11.18-slim@sha256:65bd3d9f1d7fa268dd1909973ba7eb4bdf41f6dcf2cfbe76ba9528b170f3fd79

# Runtime libraries for WeasyPrint (PDF export). Python packages,
# including SQLCipher, install from prebuilt wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# The app runs as this user, not root (L-5). The IDs should match the owner of
# the ./data folder on the host; build with your own to keep it writable:
#   docker compose build --build-arg PTVAULT_UID=$(id -u) --build-arg PTVAULT_GID=$(id -g)
ARG PTVAULT_UID=1000
ARG PTVAULT_GID=1000
# --non-unique: the host's IDs may already exist in the image (macOS gives
# GID 20, which is "dialout" here), and the user still has to match them.
RUN groupadd --non-unique --gid "${PTVAULT_GID}" ptvault \
    && useradd --non-unique --uid "${PTVAULT_UID}" --gid "${PTVAULT_GID}" --no-create-home \
       --home-dir /app --shell /usr/sbin/nologin ptvault

# Set working directory
WORKDIR /app

# Exact, hash-checked dependencies (L-6); requirements.txt lists the top level
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

# Application code stays owned by root, so the app cannot modify itself
COPY . .

# Writable by the app: its data (database, keys, uploads, Atomics) and the
# CyberChef install folder
RUN mkdir -p /app/data/uploads /app/static/tools \
    && chown -R ptvault:ptvault /app/data /app/static/tools

USER ptvault

# Expose port
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/app/data/ptvault.db
ENV ENVIRONMENT=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health')" || exit 1

# Run the application (listen on all interfaces inside the container)
CMD ["python", "app.py", "-i", "0.0.0.0", "-p", "5000"]
