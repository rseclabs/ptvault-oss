# PTVault Docker Image
# Production-ready containerized deployment

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt requirements-encryption.txt ./

# Install Python dependencies (including optional encryption support)
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-encryption.txt || true

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data /app/data/uploads

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

# Run the application
CMD ["python", "app.py"]
