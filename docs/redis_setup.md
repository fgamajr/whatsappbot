# Redis Setup for Production Rate Limiting

## Overview

The WhatsApp Interview Bot now supports Redis-based rate limiting for production deployments. Redis provides persistent, scalable rate limiting that works across multiple application instances.

## Features

- **Sliding Window Rate Limiting**: Uses Redis sorted sets for accurate sliding window rate limits
- **Automatic Fallback**: Falls back to in-memory rate limiting if Redis is unavailable
- **Production Ready**: Supports Redis clusters and high availability setups
- **Rate Limit Headers**: Returns standard rate limit headers to clients
- **Admin Functions**: Ability to reset rate limits for specific clients

## Configuration

### Environment Variables

Add these to your Fly secrets or environment:

```bash
# Option 1: Full Redis URL (recommended)
REDIS_URL=redis://your-redis-instance:6379/0

# Option 2: Individual components
REDIS_HOST=your-redis-host
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your-password  # if required
```

### Fly.io Setup

#### Option 1: Fly Redis (Recommended)

```bash
# Create Redis instance
fly redis create

# Set the Redis URL secret
fly secrets set REDIS_URL=redis://default:password@your-redis.flycast:6379
```

#### Option 2: External Redis (Upstash, AWS ElastiCache, etc.)

```bash
# For Upstash Redis
fly secrets set REDIS_URL=rediss://default:password@your-redis.upstash.io:6380

# For AWS ElastiCache
fly secrets set REDIS_URL=redis://your-elasticache-endpoint:6379
```

## Rate Limiting Behavior

### Default Limits
- **Per Minute**: 10 requests
- **Per Hour**: 100 requests

### Response Headers

Successful requests include:
```
X-RateLimit-Limit-Minute: 10
X-RateLimit-Remaining-Minute: 7
X-RateLimit-Limit-Hour: 100
X-RateLimit-Remaining-Hour: 85
```

Rate limited requests return:
```
HTTP 429 Too Many Requests
Retry-After: 60
X-RateLimit-Limit-Minute: 10
X-RateLimit-Limit-Hour: 100
```

## Redis Data Structure

The rate limiter uses Redis sorted sets:

```
Key: rate_limit:minute:{client_ip}
Key: rate_limit:hour:{client_ip}
Value: {timestamp: timestamp}
Score: timestamp
TTL: 60 seconds (minute) / 3600 seconds (hour)
```

## Monitoring

### Health Check

The `/health/ready` endpoint now includes Redis status:

```json
{
  "status": "healthy",
  "services": {
    "redis": {
      "status": "healthy",
      "response_time_ms": 2.34,
      "redis_version": "7.0.11",
      "connected_clients": 5,
      "used_memory_human": "1.2M"
    }
  }
}
```

### Rate Limiting Stats

You can check rate limiting statistics programmatically:

```python
from app.api.middleware.redis_rate_limiter import RedisRateLimiterMiddleware

# Get stats
stats = await rate_limiter.get_stats()
```

## Fallback Behavior

If Redis is unavailable:
- Automatically falls back to in-memory rate limiting
- Logs warning about Redis unavailability
- Continues to function normally
- Stats will show `"storage": "in_memory_fallback"`

## Production Recommendations

### Redis Configuration

For production, configure Redis with:

```redis
# redis.conf
maxmemory-policy allkeys-lru
save ""  # Disable persistence for rate limiting data
tcp-keepalive 60
timeout 0
```

### Scaling Considerations

- **Single Redis Instance**: Good for small to medium loads
- **Redis Cluster**: For high availability and large scale
- **Redis Sentinel**: For automatic failover

### Security

- Always use password authentication
- Use TLS/SSL for Redis connections in production
- Restrict Redis access to application servers only

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   ```
   Check REDIS_URL format
   Verify network connectivity
   Check Redis server status
   ```

2. **High Memory Usage**
   ```
   Redis memory grows with active IPs
   Configure maxmemory policy
   Monitor Redis memory usage
   ```

3. **Performance Issues**
   ```
   Check Redis latency
   Monitor Redis CPU usage
   Consider Redis clustering
   ```

### Debugging

Enable debug logging to see rate limiting details:

```python
import logging
logging.getLogger("app.api.middleware.redis_rate_limiter").setLevel(logging.DEBUG)
```

## Migration from In-Memory

The Redis rate limiter is a drop-in replacement. No code changes needed beyond configuration.

1. Deploy with Redis configuration
2. Monitor logs for successful Redis connection
3. Verify rate limiting works via headers
4. Old in-memory limits are automatically discarded

## Cost Optimization

### Upstash (Pay-per-request)
- Good for low to medium traffic
- Automatic scaling
- Global edge locations

### Fly Redis (Fixed cost)
- Predictable pricing
- Co-located with app
- Good for consistent traffic

### AWS ElastiCache (Reserved instances)
- Lowest cost for high traffic
- Requires AWS setup
- Best for enterprise deployments

## Example Configurations

### Development
```bash
# Local Redis
REDIS_URL=redis://localhost:6379/0
```

### Staging
```bash
# Fly Redis
REDIS_URL=redis://default:password@redis-staging.flycast:6379
```

### Production
```bash
# Upstash with TLS
REDIS_URL=rediss://default:password@redis-prod.upstash.io:6380
```