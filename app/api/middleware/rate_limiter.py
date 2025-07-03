import time
import logging
from typing import Dict, Optional
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
from app.utils.secure_logging import SecureLogger

logger = logging.getLogger(__name__)

class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware to prevent abuse"""
    
    def __init__(self, app, requests_per_minute: int = None, requests_per_hour: int = None):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute or settings.RATE_LIMIT_PER_MINUTE
        self.requests_per_hour = requests_per_hour or settings.RATE_LIMIT_PER_HOUR
        
        # In-memory storage for simplicity (use Redis in production)
        self.minute_requests: Dict[str, list] = {}
        self.hour_requests: Dict[str, list] = {}
        
        SecureLogger.safe_log_info(logger, "Rate limiter initialized", {
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
            
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later."
            )
        
        # Process request
        response = await call_next(request)
        return response
    
    async def _check_rate_limit(self, client_ip: str) -> bool:
        """Check if client IP is within rate limits"""
        current_time = time.time()
        
        # Initialize tracking for new IPs
        if client_ip not in self.minute_requests:
            self.minute_requests[client_ip] = []
        if client_ip not in self.hour_requests:
            self.hour_requests[client_ip] = []
        
        # Clean old entries
        self._cleanup_old_requests(client_ip, current_time)
        
        # Check minute limit
        if len(self.minute_requests[client_ip]) >= self.requests_per_minute:
            return False
        
        # Check hour limit
        if len(self.hour_requests[client_ip]) >= self.requests_per_hour:
            return False
        
        # Add current request
        self.minute_requests[client_ip].append(current_time)
        self.hour_requests[client_ip].append(current_time)
        
        return True
    
    def _cleanup_old_requests(self, client_ip: str, current_time: float):
        """Remove old requests outside the time windows"""
        # Remove requests older than 1 minute
        minute_cutoff = current_time - 60
        self.minute_requests[client_ip] = [
            req_time for req_time in self.minute_requests[client_ip]
            if req_time > minute_cutoff
        ]
        
        # Remove requests older than 1 hour
        hour_cutoff = current_time - 3600
        self.hour_requests[client_ip] = [
            req_time for req_time in self.hour_requests[client_ip]
            if req_time > hour_cutoff
        ]
    
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
    
    def get_stats(self) -> Dict[str, int]:
        """Get current rate limiting statistics"""
        return {
            'tracked_ips': len(self.minute_requests),
            'total_minute_requests': sum(len(reqs) for reqs in self.minute_requests.values()),
            'total_hour_requests': sum(len(reqs) for reqs in self.hour_requests.values())
        }