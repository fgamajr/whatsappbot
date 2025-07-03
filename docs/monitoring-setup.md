# Complete Monitoring Stack Setup

## Overview

This guide covers the complete monitoring infrastructure for the WhatsApp Interview Bot, including Prometheus metrics, Grafana dashboards, Alertmanager notifications, and auto-scaling capabilities.

## Architecture

```
WhatsApp Bot → Prometheus Metrics → Grafana Dashboards
                    ↓
               Alertmanager → Notifications (Email/Slack/WebSocket)
                    ↓
            Auto-scaling Actions (Docker/K8s/Fly.io)
```

## Quick Start

### 1. Start Monitoring Stack

```bash
# Start full monitoring infrastructure
docker-compose -f docker-compose.monitoring.yml up -d

# Verify services
docker-compose -f docker-compose.monitoring.yml ps
```

### 2. Access Dashboards

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093
- **Application Metrics**: http://localhost:8001/metrics

### 3. Start Application with Monitoring

```bash
# Start the application (auto-starts monitoring services)
python -m app.main

# Or with Docker Compose
docker-compose -f docker-compose.celery.yml up -d
```

## Monitoring Components

### 1. Prometheus Metrics (`app/infrastructure/prometheus_metrics.py`)

#### Available Metrics

**Task Metrics:**
- `celery_tasks_total`: Total number of tasks by status
- `celery_task_duration_seconds`: Task execution duration histogram
- `celery_task_retries_total`: Task retry counter

**Queue Metrics:**
- `celery_queue_length`: Current queue length
- `celery_queue_processing_seconds`: Queue processing time summary

**Worker Metrics:**
- `celery_worker_active_tasks`: Active tasks per worker
- `celery_worker_processed_tasks_total`: Total processed tasks
- `celery_worker_memory_usage_bytes`: Worker memory usage
- `celery_worker_cpu_usage_percent`: Worker CPU usage

**System Metrics:**
- `celery_system_total_workers`: Total active workers
- `celery_system_total_queued_tasks`: Total queued tasks
- `celery_system_throughput_per_minute`: System throughput
- `celery_system_error_rate_percent`: System error rate

**Pipeline Metrics:**
- `celery_pipeline_duration_seconds`: Complete pipeline duration
- `celery_pipeline_success_rate_percent`: Pipeline success rate

**Auto-scaling Metrics:**
- `celery_autoscaling_decisions_total`: Auto-scaling decisions
- `celery_autoscaling_target_workers`: Target worker count

**WebSocket Metrics:**
- `websocket_active_connections`: Active WebSocket connections
- `websocket_messages_sent_total`: Total WebSocket messages

#### Automatic Collection

Metrics are automatically collected every 30 seconds and exposed on port 8001:

```python
# Automatic task metrics collection
@prometheus_task_metrics
def my_celery_task():
    # Task implementation
    pass

# Automatic pipeline metrics
@prometheus_pipeline_metrics("audio_processing")
def process_audio_pipeline():
    # Pipeline implementation
    pass
```

### 2. Grafana Dashboards

#### Main Dashboard: "Celery WhatsApp Bot Overview"

**Panels:**
1. **System Overview**: Active workers and queued tasks
2. **System Performance**: Throughput and error rates
3. **Queue Lengths**: Real-time queue monitoring
4. **Worker Activity**: Active tasks per worker
5. **Task Success/Failure Rates**: Task completion metrics
6. **Pipeline Duration**: Processing time percentiles
7. **Auto-scaling Target Workers**: Scaling decisions
8. **WebSocket Connections**: Real-time connection counts

**Access:** http://localhost:3000/d/celery-overview

#### Dashboard Features:
- **Auto-refresh**: 5-second intervals
- **Time range**: Last 1 hour (configurable)
- **Variables**: Filter by worker, queue, pipeline type
- **Annotations**: Mark scaling events and deployments

### 3. Alerting Rules (`prometheus/alert_rules.yml`)

#### Critical Alerts:
- **NoActiveWorkers**: No workers for 2+ minutes
- **LowDiskSpace**: Disk usage > 90%

#### Warning Alerts:
- **HighQueueLength**: Queue length > 10 for 5+ minutes
- **HighErrorRate**: Error rate > 10% for 5+ minutes
- **LongPipelineDuration**: 95th percentile > 30 minutes
- **HighTaskFailureRate**: Failure rate > 10%
- **AutoScalingStuck**: No scaling decisions despite high load
- **HighCPUUsage**: CPU > 80% for 5+ minutes
- **HighMemoryUsage**: Memory > 85% for 5+ minutes

#### Alert Configuration:
```yaml
- alert: HighQueueLength
  expr: celery_queue_length > 10
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "High queue length detected"
    description: "Queue {{ $labels.queue_name }} has {{ $value }} tasks waiting"
```

### 4. Alertmanager Notifications

#### Supported Channels:
- **WebSocket**: Real-time dashboard notifications
- **Email**: SMTP-based alerts
- **Slack**: Webhook integration
- **Webhook**: Custom integrations

#### Configuration Example:
```yaml
route:
  group_by: ['alertname']
  group_wait: 10s
  repeat_interval: 1h
  receiver: 'web.hook'

receivers:
- name: 'web.hook'
  webhook_configs:
  - url: 'http://host.docker.internal:8000/alerts/webhook'
```

## API Endpoints

### Monitoring Endpoints (`/monitoring/*`)

#### System Status
```bash
# Health check
GET /monitoring/health

# Current metrics snapshot
GET /monitoring/metrics/current

# Comprehensive system overview
GET /monitoring/system/overview

# Performance report
GET /monitoring/performance/report
```

#### Auto-scaling Control
```bash
# Get auto-scaling status
GET /monitoring/auto-scaling/status

# Enable/disable auto-scaling
POST /monitoring/auto-scaling/toggle
{
  "enable": true
}
```

#### WebSocket Management
```bash
# WebSocket connection statistics
GET /monitoring/websockets/stats
```

#### Prometheus Control
```bash
# Start Prometheus metrics server
POST /monitoring/prometheus/start
{
  "port": 8001
}
```

### Example Responses

#### System Overview:
```json
{
  "status": "success",
  "data": {
    "health_score": 85,
    "metrics": {
      "queues": {
        "audio_processing": {
          "length": 3,
          "workers_active": 2,
          "avg_processing_time": 300.5
        }
      },
      "system": {
        "total_workers": 5,
        "throughput_per_minute": 8.2,
        "error_rate": 2.1
      }
    },
    "auto_scaling": {
      "enabled": true,
      "recent_decisions": [...]
    },
    "recommendations": [
      "Enable auto-scaling for better capacity management"
    ]
  }
}
```

## Auto-scaling Integration

### Scaling Rules Configuration

```python
scaling_rules = {
    'audio_processing': ScalingRule(
        queue_name='audio_processing',
        min_workers=2,
        max_workers=8,
        scale_up_threshold=3.0,    # Scale up if >3 tasks queued
        scale_down_threshold=0.5,  # Scale down if <0.5 avg tasks
        cpu_threshold=75.0,
        memory_threshold=80.0,
        cooldown_minutes=3
    )
}
```

### Deployment Support

**Docker Compose:**
```bash
docker-compose -f docker-compose.celery.yml up -d --scale celery-worker-audio=5
```

**Kubernetes:**
```bash
kubectl scale deployment celery-worker-audio --replicas=5
```

**Fly.io:**
```bash
fly scale count 5 --app whatsapp-interview-bot
```

## Performance Optimization

### 1. Metrics Collection Optimization

```python
# Adjust collection frequency
metrics_collector.collection_interval = 15  # seconds

# Limit metrics history
metrics_collector.system_metrics_history = deque(maxlen=500)
```

### 2. Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s  # Adjust based on needs
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'whatsapp-bot'
    scrape_interval: 15s
    scrape_timeout: 10s
```

### 3. Grafana Performance

- **Auto-refresh**: Balance between real-time and performance
- **Query optimization**: Use rate() and histogram_quantile()
- **Panel limits**: Limit data points per panel

## Troubleshooting

### Common Issues

#### 1. Metrics Not Appearing
```bash
# Check Prometheus metrics endpoint
curl http://localhost:8001/metrics

# Verify Prometheus target health
curl http://localhost:9090/api/v1/targets
```

#### 2. High Memory Usage
```bash
# Monitor metrics collector memory
GET /monitoring/system/overview

# Reduce collection frequency
POST /monitoring/prometheus/start {"port": 8001}
```

#### 3. Grafana Dashboard Issues
```bash
# Check Grafana logs
docker logs whatsapp-bot-grafana

# Verify Prometheus data source
curl http://localhost:3000/api/datasources
```

#### 4. Auto-scaling Not Working
```bash
# Check auto-scaler status
GET /monitoring/auto-scaling/status

# Enable auto-scaling
POST /monitoring/auto-scaling/toggle {"enable": true}

# Check scaling decisions
GET /monitoring/performance/report
```

### Debug Commands

```bash
# Check all monitoring services
docker-compose -f docker-compose.monitoring.yml ps

# View Prometheus configuration
curl http://localhost:9090/api/v1/status/config

# Check alert rules
curl http://localhost:9090/api/v1/rules

# View active alerts
curl http://localhost:9090/api/v1/alerts
```

## Production Deployment

### Security Considerations

1. **Authentication**: Enable authentication for Grafana
2. **Network Security**: Use reverse proxy for external access
3. **Data Retention**: Configure appropriate retention policies
4. **Secret Management**: Use secure credential storage

### High Availability

1. **Prometheus**: Use federation for multiple instances
2. **Grafana**: Configure database backend
3. **Alertmanager**: Cluster configuration for redundancy

### Example Production Config

```yaml
# Production Grafana configuration
environment:
  - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
  - GF_INSTALL_PLUGINS=grafana-piechart-panel
  - GF_USERS_ALLOW_SIGN_UP=false
  - GF_AUTH_ANONYMOUS_ENABLED=false
  - GF_SMTP_ENABLED=true
  - GF_SMTP_HOST=smtp.company.com:587
```

## Scaling Recommendations

### Small Deployment (< 100 tasks/day)
- **Workers**: 2-3 workers total
- **Monitoring**: Basic metrics only
- **Collection**: 60-second intervals

### Medium Deployment (100-1000 tasks/day)
- **Workers**: 5-10 workers with specialization
- **Monitoring**: Full stack with alerting
- **Collection**: 30-second intervals

### Large Deployment (> 1000 tasks/day)
- **Workers**: 10+ workers with auto-scaling
- **Monitoring**: Multi-instance with federation
- **Collection**: 15-second intervals
- **Storage**: Dedicated metrics storage

## Next Steps

1. **Custom Dashboards**: Create role-specific dashboards
2. **Advanced Alerting**: Implement alert routing and escalation
3. **Capacity Planning**: Use historical data for forecasting
4. **Performance Tuning**: Optimize based on metrics insights
5. **Integration**: Connect with existing monitoring systems