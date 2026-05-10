# Production Dockerfile for VidGrab - YouTube & TikTok Downloader
FROM python:3.12-slim

# Install system dependencies (ffmpeg for video processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create downloads directory
RUN mkdir -p /tmp/vidgrab_downloads

# Expose the port Render uses
EXPOSE 10000

# Run with Gunicorn (gevent workers for SSE support)
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "2", "--worker-class", "gevent", "--timeout", "300", "--keep-alive", "65", "app:app"]
