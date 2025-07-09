# YouTube Downloader Migration Strategy

## Overview

This document outlines the migration strategy from the current embedded yt-dlp implementation to a resilient, containerized service approach.

## Current Issues

1. **yt-dlp gets outdated** - YouTube changes signing methods regularly
2. **Tight coupling** - yt-dlp is embedded in the main application
3. **No update mechanism** - Manual updates required
4. **Single point of failure** - If yt-dlp breaks, entire app affected

## New Architecture

### 1. Containerized Service
- **yt-dlp runs in separate container**
- **Auto-update mechanism** via cron jobs
- **Health checks** and monitoring
- **Isolated failures** don't affect main app

### 2. Resilient Client
- **Retry logic** with exponential backoff
- **Health checks** before downloads
- **Automatic fallbacks** to alternative approaches
- **Graceful error handling**

### 3. Monitoring & Updates
- **Automatic updates** every 6 hours
- **Health monitoring** every 30 minutes
- **Logging** for debugging and analysis
- **Alerts** for failures

## Migration Steps

### Phase 1: Setup Infrastructure
```bash
# 1. Build and deploy yt-dlp service
chmod +x scripts/deploy-ytdlp.sh
./scripts/deploy-ytdlp.sh

# 2. Test service
curl http://localhost:8080/health
```

### Phase 2: Update Application Code
```python
# Replace in app/api/v1/messaging.py
from app.services.resilient_youtube_downloader import resilient_youtube_service

# Replace youtube_service with resilient_youtube_service
video_data, metadata = await resilient_youtube_service.download_video(url, progress_callback)
```

### Phase 3: Configuration Updates
```bash
# Add to .env
YTDLP_SERVICE_URL=http://localhost:8080
YTDLP_AUTO_UPDATE=true
YTDLP_UPDATE_INTERVAL_HOURS=6
```

### Phase 4: Monitoring Setup
```bash
# Monitor service health
curl http://localhost:8080/health

# Manual update
curl -X POST http://localhost:8080/update

# Check logs
docker-compose -f docker-compose.ytdlp.yml logs -f yt-dlp-service
```

## Benefits

### 1. **Automatic Updates**
- yt-dlp stays current with YouTube changes
- No manual intervention required
- Reduces downtime from broken downloads

### 2. **Fault Tolerance**
- Service failures don't crash main app
- Automatic retries with backoff
- Health checks prevent cascading failures

### 3. **Scalability**
- Service can be scaled independently
- Multiple instances for high availability
- Load balancing possible

### 4. **Maintainability**
- Clear separation of concerns
- Easier debugging and monitoring
- Independent deployment cycles

## Configuration Options

### Environment Variables
```bash
# Service URL
YTDLP_SERVICE_URL=http://localhost:8080

# Auto-update settings
YTDLP_AUTO_UPDATE=true
YTDLP_UPDATE_INTERVAL_HOURS=6

# Download constraints
YOUTUBE_MAX_DURATION=7200
YOUTUBE_MAX_FILE_SIZE=209715200
YOUTUBE_QUALITY="best[ext=mp4][height<=720]/best[ext=mp4]/best[height<=720]/best"
```

### Docker Compose Settings
```yaml
# Resource limits
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '0.5'

# Health checks
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

## Monitoring & Troubleshooting

### Health Checks
```bash
# Service health
curl http://localhost:8080/health

# Container health
docker ps | grep yt-dlp

# Logs
docker-compose -f docker-compose.ytdlp.yml logs -f
```

### Common Issues

1. **Service Not Starting**
   - Check Docker logs
   - Verify port availability
   - Check resource limits

2. **Download Failures**
   - Check yt-dlp version
   - Try manual update
   - Check YouTube URL validity

3. **High Memory Usage**
   - Adjust resource limits
   - Monitor concurrent downloads
   - Check for memory leaks

## Rollback Strategy

If issues occur, you can rollback to the original implementation:

```python
# Temporarily revert to original service
from app.services.youtube_downloader import youtube_service

# Use original service
video_data, metadata = await youtube_service.download_video(url, progress_callback)
```

## Future Enhancements

1. **Multiple Service Instances** - Load balancing
2. **Advanced Caching** - Cache successful downloads
3. **Priority Queues** - Handle urgent downloads first
4. **Metrics & Analytics** - Download success rates
5. **Alternative Services** - Fallback to other download methods