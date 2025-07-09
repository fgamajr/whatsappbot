# Dockerfile for yt-dlp service
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp (always latest)
RUN pip install --upgrade yt-dlp

# Create update script
COPY update-yt-dlp.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/update-yt-dlp.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import yt_dlp; print('OK')" || exit 1

# API service
COPY yt-dlp-service.py /app/
WORKDIR /app

EXPOSE 8080

CMD ["python", "yt-dlp-service.py"]