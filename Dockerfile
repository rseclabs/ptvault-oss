# PTVault Docker Image
# Production-ready containerized deployment

FROM python:3.11-slim

# Runtime libraries for WeasyPrint (PDF export). Python packages,
# including SQLCipher, install from prebuilt wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt ./

# Install Python dependencies (includes sqlcipher3 for database encryption)
RUN pip install --no-cache-dir -r requirements.txt

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

# Run the application (listen on all interfaces inside the container)
CMD ["python", "app.py", "-i", "0.0.0.0", "-p", "5000"]
