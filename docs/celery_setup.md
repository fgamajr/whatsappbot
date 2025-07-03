# Celery Setup Documentation

## Overview

The WhatsApp Interview Bot now supports Celery for distributed task processing, providing better scalability, reliability, and monitoring capabilities.

## Phase 1: Basic Infrastructure ✅

This phase implements the foundational Celery infrastructure while maintaining full compatibility with existing FastAPI background tasks.

### Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │  Celery Worker  │    │  Celery Worker  │
│   (Webhooks)    │    │ (Audio Proc.)   │    │ (Doc Gen.)      │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼───────────┐
                    │       Redis Broker      │
                    │   DB 1: Task Queue      │
                    │   DB 2: Task Results    │
                    │   DB 0: Rate Limiting   │
                    └─────────────────────────┘
```

### Queue Structure

- **default**: General purpose tasks
- **audio_processing**: Long-running audio transcription and analysis
- **document_generation**: Document creation tasks
- **maintenance**: System maintenance and health checks
- **high_priority**: Urgent tasks (user-facing operations)

## Installation

### 1. Dependencies

The required dependencies are already added to `requirements.txt`:

```
celery[redis]==5.3.4
flower==2.0.1
kombu==5.3.4
```

### 2. Redis Configuration

Redis is configured with separate databases:

- **DB 0**: Rate limiting (existing)
- **DB 1**: Celery message broker
- **DB 2**: Celery task results

### 3. Environment Variables

Add to your `.env` file or Fly secrets:

```bash
# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Optional: Override default task settings
CELERY_TASK_SOFT_TIME_LIMIT=1800  # 30 minutes
CELERY_TASK_TIME_LIMIT=2100       # 35 minutes
CELERY_TASK_MAX_RETRIES=3
```

## Development Setup

### Quick Start

```bash
# Start all services with Celery
./scripts/start-celery-dev.sh

# Or manually with docker-compose
docker-compose -f docker-compose.celery.yml up -d --build
```

### Service Breakdown

1. **redis**: Message broker and result backend
2. **app**: FastAPI application (port 8000)
3. **celery-worker-audio**: Handles audio processing (2 workers)
4. **celery-worker-docs**: Handles document generation (3 workers)
5. **celery-worker-general**: Handles default and maintenance tasks (4 workers)
6. **celery-beat**: Periodic task scheduler
7. **flower**: Web-based monitoring (port 5555)

## Testing Celery

### Health Check

```bash
curl http://localhost:8000/health/ready
```

### Simple Task Test

```bash
curl -X POST http://localhost:8000/celery/test \
  -H 'Content-Type: application/json' \
  -d '{"x": 4, "y": 4}'
```

Response:
```json
{
  "task_id": "abc-123-def",
  "status": "pending",
  "message": "Test task started: 4 + 4"
}
```

### Check Task Status

```bash
curl http://localhost:8000/celery/status/abc-123-def
```

Response:
```json
{
  "task_id": "abc-123-def",
  "status": "SUCCESS",
  "result": {
    "status": "success",
    "result": 8,
    "task_id": "abc-123-def"
  }
}
```

## Monitoring

### Flower Web UI

Access Flower at http://localhost:5555

- **Username**: admin
- **Password**: admin123

Features:
- Real-time task monitoring
- Worker statistics
- Queue management
- Task history and details

### Worker Statistics

```bash
curl http://localhost:8000/celery/worker-stats
```

### Queue Information

```bash
curl http://localhost:8000/celery/queue-info
```

## Available Tasks

### Audio Processing

```python
from app.tasks.audio_processing import process_audio_message_task

# Schedule audio processing
task = process_audio_message_task.delay(message_data)
```

### Document Generation

```python
from app.tasks.document_generation import generate_documents_task

# Generate documents
task = generate_documents_task.delay(transcript_data, analysis_data, interview_id)
```

### Maintenance Tasks

```python
from app.tasks.maintenance import health_check_task, redis_memory_check_task

# System health check
health_task = health_check_task.delay()

# Redis memory check
memory_task = redis_memory_check_task.delay()
```

### Recovery Tasks

```python
from app.tasks.recovery import check_orphaned_interviews_task, recover_interview_task

# Check for orphaned interviews
check_task = check_orphaned_interviews_task.delay()

# Recover specific interview
recover_task = recover_interview_task.delay(interview_id)
```

## Configuration Details

### Task Routing

Tasks are automatically routed to appropriate queues:

```python
CELERY_TASK_ROUTES = {
    'app.tasks.audio_processing.*': {'queue': 'audio_processing'},
    'app.tasks.document_generation.*': {'queue': 'document_generation'},
    'app.tasks.recovery.*': {'queue': 'maintenance'},
    'app.tasks.maintenance.*': {'queue': 'maintenance'},
}
```

### Worker Configuration

- **Prefetch Multiplier**: 1 (fair distribution)
- **Acknowledgment**: Late acks enabled for reliability
- **Retry Policy**: Exponential backoff with jitter
- **Time Limits**: 30-minute soft / 35-minute hard limits

### Security Features

- **Secure Logging**: Sensitive data automatically redacted
- **Input Validation**: All task inputs validated and sanitized
- **Error Handling**: Comprehensive error tracking and reporting
- **Task Monitoring**: Complete task lifecycle logging

## Troubleshooting

### Check Worker Health

```bash
docker-compose -f docker-compose.celery.yml exec celery-worker-general \
  celery -A app.celery_app inspect ping
```

### View Worker Logs

```bash
docker-compose -f docker-compose.celery.yml logs -f celery-worker-audio
```

### Redis Connection Issues

```bash
# Test Redis connectivity
docker-compose -f docker-compose.celery.yml exec redis redis-cli ping

# Check Redis databases
docker-compose -f docker-compose.celery.yml exec redis redis-cli info keyspace
```

### Clear All Queues (Development Only)

```bash
docker-compose -f docker-compose.celery.yml exec celery-worker-general \
  celery -A app.celery_app purge -f
```

## Next Phases

### Phase 2: Task Decomposition
- Break down audio processing into smaller, parallel tasks
- Implement chain and group patterns for complex workflows
- Add progress tracking for long-running operations

### Phase 3: Production Optimization
- Implement auto-scaling based on queue length
- Add comprehensive monitoring and alerting
- Optimize task routing and resource allocation

## Production Deployment

### Fly.io Configuration

```bash
# Set Redis URLs as Fly secrets
fly secrets set CELERY_BROKER_URL="redis://your-redis:6379/1"
fly secrets set CELERY_RESULT_BACKEND="redis://your-redis:6379/2"

# Deploy with Celery workers
fly deploy --config fly.celery.toml
```

### Scaling Workers

```bash
# Scale audio processing workers
docker-compose -f docker-compose.celery.yml up -d --scale celery-worker-audio=5

# Scale document generation workers  
docker-compose -f docker-compose.celery.yml up -d --scale celery-worker-docs=3
```

## Security Considerations

1. **Redis Security**: Use password authentication in production
2. **Flower Access**: Change default credentials and use HTTPS
3. **Task Data**: Sensitive data is automatically sanitized in logs
4. **Network Isolation**: Use private networks for Redis connections
5. **Resource Limits**: Configure appropriate memory and CPU limits

## Performance Tips

1. **Queue Separation**: Use dedicated workers for different task types
2. **Concurrency Tuning**: Adjust worker concurrency based on task type (CPU vs I/O bound)
3. **Prefetch Settings**: Keep prefetch low for long-running tasks
4. **Monitoring**: Use Flower and custom metrics to optimize performance
5. **Resource Allocation**: Scale workers based on queue depth and processing time