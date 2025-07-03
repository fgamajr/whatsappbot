import time
import logging
from typing import Dict, Optional, List
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
from app.utils.secure_logging import SecureLogger
from app.infrastructure.redis_client import redis_client

logger = logging.getLogger(__name__)

class RedisRateLimiterMiddleware(BaseHTTPMiddleware):
    """Redis-based rate limiting middleware for production use"""
    
    def __init__(self, app, requests_per_minute: int = None, requests_per_hour: int = None):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute or settings.RATE_LIMIT_PER_MINUTE
        self.requests_per_hour = requests_per_hour or settings.RATE_LIMIT_PER_HOUR
        
        # Fallback to in-memory storage if Redis is not available
        self.fallback_minute_requests: Dict[str, list] = {}
        self.fallback_hour_requests: Dict[str, list] = {}
        
        SecureLogger.safe_log_info(logger, "Redis rate limiter initialized", {
            'requests_per_minute': self.requests_per_minute,
            'requests_per_hour': self.requests_per_hour
        })
    
    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Check rate limits
        if not await self._check_rate_limit(client_ip):
            SecureLogger.safe_log_warning(logger, "Rate limit exceeded", {
                'client_ip': client_ip,
                'path': request.url.path,
                'method': request.method
            })
            
            # Add rate limit headers
            response = Response(
                content='{"detail": "Rate limit exceeded. Please try again later."}',
                status_code=429,
                media_type="application/json"
            )
            response.headers["Retry-After"] = "60"
            response.headers["X-RateLimit-Limit-Minute"] = str(self.requests_per_minute)
            response.headers["X-RateLimit-Limit-Hour"] = str(self.requests_per_hour)
            return response
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to successful responses
        remaining_minute, remaining_hour = await self._get_remaining_requests(client_ip)
        if remaining_minute is not None:
            response.headers["X-RateLimit-Limit-Minute"] = str(self.requests_per_minute)
            response.headers["X-RateLimit-Remaining-Minute"] = str(remaining_minute)
        if remaining_hour is not None:
            response.headers["X-RateLimit-Limit-Hour"] = str(self.requests_per_hour)
            response.headers["X-RateLimit-Remaining-Hour"] = str(remaining_hour)
        
        return response
    
    async def _check_rate_limit(self, client_ip: str) -> bool:
        """Check if client IP is within rate limits using Redis"""
        current_time = int(time.time())
        
        # Try Redis first
        if await redis_client.is_connected():
            return await self._check_rate_limit_redis(client_ip, current_time)
        else:
            # Fallback to in-memory storage
            SecureLogger.safe_log_warning(logger, "Redis unavailable, using fallback rate limiting")
            return await self._check_rate_limit_fallback(client_ip, current_time)
    
    async def _check_rate_limit_redis(self, client_ip: str, current_time: int) -> bool:
        """Redis-based rate limiting with sliding window"""
        minute_key = f"rate_limit:minute:{client_ip}"
        hour_key = f"rate_limit:hour:{client_ip}"
        
        try:
            # Use Redis pipeline for atomic operations
            async with redis_client.pipeline() as pipe:
                # Remove old entries and count current requests
                minute_cutoff = current_time - 60
                hour_cutoff = current_time - 3600
                
                # Remove old entries
                await pipe.zremrangebyscore(minute_key, 0, minute_cutoff)
                await pipe.zremrangebyscore(hour_key, 0, hour_cutoff)
                
                # Count current requests
                await pipe.zcard(minute_key)
                await pipe.zcard(hour_key)
                
                # Execute pipeline
                results = await pipe.execute()
                
                minute_count = results[2] if len(results) > 2 else 0
                hour_count = results[3] if len(results) > 3 else 0
                
                # Check limits
                if minute_count >= self.requests_per_minute:
                    return False
                
                if hour_count >= self.requests_per_hour:
                    return False
                
                # Add current request with score as timestamp
                await redis_client._redis.zadd(minute_key, {str(current_time): current_time})
                await redis_client._redis.zadd(hour_key, {str(current_time): current_time})
                
                # Set expiration
                await redis_client.expire(minute_key, 60)
                await redis_client.expire(hour_key, 3600)
                
                return True
                
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Redis rate limiting failed", e)
            # Fallback to in-memory on Redis errors
            return await self._check_rate_limit_fallback(client_ip, current_time)
    
    async def _check_rate_limit_fallback(self, client_ip: str, current_time: int) -> bool:
        """Fallback in-memory rate limiting"""
        # Initialize tracking for new IPs
        if client_ip not in self.fallback_minute_requests:
            self.fallback_minute_requests[client_ip] = []
        if client_ip not in self.fallback_hour_requests:
            self.fallback_hour_requests[client_ip] = []
        
        # Clean old entries
        self._cleanup_fallback_requests(client_ip, current_time)
        
        # Check limits
        if len(self.fallback_minute_requests[client_ip]) >= self.requests_per_minute:
            return False
        
        if len(self.fallback_hour_requests[client_ip]) >= self.requests_per_hour:
            return False
        
        # Add current request
        self.fallback_minute_requests[client_ip].append(current_time)
        self.fallback_hour_requests[client_ip].append(current_time)
        
        return True
    
    def _cleanup_fallback_requests(self, client_ip: str, current_time: int):
        """Clean old requests from fallback storage"""
        minute_cutoff = current_time - 60
        hour_cutoff = current_time - 3600
        
        self.fallback_minute_requests[client_ip] = [
            req_time for req_time in self.fallback_minute_requests[client_ip]
            if req_time > minute_cutoff
        ]
        
        self.fallback_hour_requests[client_ip] = [
            req_time for req_time in self.fallback_hour_requests[client_ip]
            if req_time > hour_cutoff
        ]
    
    async def _get_remaining_requests(self, client_ip: str) -> tuple[Optional[int], Optional[int]]:
        """Get remaining requests for client IP"""
        if await redis_client.is_connected():
            try:
                minute_key = f"rate_limit:minute:{client_ip}"
                hour_key = f"rate_limit:hour:{client_ip}"
                
                current_time = int(time.time())
                minute_cutoff = current_time - 60
                hour_cutoff = current_time - 3600
                
                # Count current requests
                minute_count = await redis_client._redis.zcount(minute_key, minute_cutoff, current_time)
                hour_count = await redis_client._redis.zcount(hour_key, hour_cutoff, current_time)
                
                remaining_minute = max(0, self.requests_per_minute - minute_count)
                remaining_hour = max(0, self.requests_per_hour - hour_count)
                
                return remaining_minute, remaining_hour
                
            except Exception as e:
                SecureLogger.safe_log_error(logger, "Failed to get remaining requests", e)
                return None, None
        else:
            # Fallback calculation
            minute_remaining = max(0, self.requests_per_minute - len(self.fallback_minute_requests.get(client_ip, [])))
            hour_remaining = max(0, self.requests_per_hour - len(self.fallback_hour_requests.get(client_ip, [])))
            return minute_remaining, hour_remaining
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        # Check for forwarded headers first (common in production)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
            
        # Fallback to client IP
        if request.client:
            return request.client.host
            
        return "unknown"
    
    async def get_stats(self) -> Dict[str, any]:
        """Get current rate limiting statistics"""
        if await redis_client.is_connected():
            try:
                # Get Redis stats
                info = await redis_client._redis.info('keyspace')
                
                return {
                    'storage': 'redis',
                    'redis_connected': True,
                    'keyspace_info': info,
                    'requests_per_minute_limit': self.requests_per_minute,
                    'requests_per_hour_limit': self.requests_per_hour
                }
            except Exception as e:
                return {
                    'storage': 'redis',
                    'redis_connected': False,
                    'error': str(e)
                }
        else:
            return {
                'storage': 'in_memory_fallback',
                'redis_connected': False,
                'tracked_ips': len(self.fallback_minute_requests),
                'total_minute_requests': sum(len(reqs) for reqs in self.fallback_minute_requests.values()),
                'total_hour_requests': sum(len(reqs) for reqs in self.fallback_hour_requests.values())
            }
    
    async def reset_client_limits(self, client_ip: str) -> bool:
        """Reset rate limits for a specific client (admin function)"""
        if await redis_client.is_connected():
            try:
                minute_key = f"rate_limit:minute:{client_ip}"
                hour_key = f"rate_limit:hour:{client_ip}"
                
                await redis_client.delete(minute_key)
                await redis_client.delete(hour_key)
                
                SecureLogger.safe_log_info(logger, "Rate limits reset for client", {
                    'client_ip': client_ip
                })
                return True
                
            except Exception as e:
                SecureLogger.safe_log_error(logger, "Failed to reset rate limits", e)
                return False
        else:
            # Reset fallback storage
            self.fallback_minute_requests.pop(client_ip, None)
            self.fallback_hour_requests.pop(client_ip, None)
            return True