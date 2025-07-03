import logging
import redis.asyncio as redis
from typing import Optional, Any
from contextlib import asynccontextmanager
from app.core.config import settings
from app.utils.secure_logging import SecureLogger

logger = logging.getLogger(__name__)

class RedisClient:
    """Redis client for caching and rate limiting"""
    
    _instance: Optional['RedisClient'] = None
    _redis: Optional[redis.Redis] = None
    
    def __new__(cls) -> 'RedisClient':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def connect(self):
        """Initialize Redis connection"""
        if self._redis is not None:
            return
        
        try:
            # Parse Redis URL or use individual components
            if hasattr(settings, 'REDIS_URL') and settings.REDIS_URL:
                self._redis = redis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
            else:
                # Fallback to individual settings
                self._redis = redis.Redis(
                    host=getattr(settings, 'REDIS_HOST', 'localhost'),
                    port=getattr(settings, 'REDIS_PORT', 6379),
                    db=getattr(settings, 'REDIS_DB', 0),
                    password=getattr(settings, 'REDIS_PASSWORD', None),
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
            
            # Test connection
            await self._redis.ping()
            
            SecureLogger.safe_log_info(logger, "Redis connection established")
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to connect to Redis", e, {
                'fallback': 'Will use in-memory storage'
            })
            self._redis = None
    
    async def disconnect(self):
        """Close Redis connection"""
        if self._redis:
            await self._redis.aclose()
            self._redis = None
            SecureLogger.safe_log_info(logger, "Redis connection closed")
    
    async def is_connected(self) -> bool:
        """Check if Redis is connected"""
        if not self._redis:
            return False
        
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from Redis"""
        if not self._redis:
            return None
        
        try:
            return await self._redis.get(key)
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Redis GET failed", e, {'key': key})
            return None
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set value in Redis with optional expiration"""
        if not self._redis:
            return False
        
        try:
            await self._redis.set(key, value, ex=expire)
            return True
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Redis SET failed", e, {
                'key': key,
                'expire': expire
            })
            return False
    
    async def incr(self, key: str) -> Optional[int]:
        """Increment value in Redis"""
        if not self._redis:
            return None
        
        try:
            return await self._redis.incr(key)
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Redis INCR failed", e, {'key': key})
            return None
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on a key"""
        if not self._redis:
            return False
        
        try:
            return await self._redis.expire(key, seconds)
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Redis EXPIRE failed", e, {
                'key': key,
                'seconds': seconds
            })
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis"""
        if not self._redis:
            return False
        
        try:
            result = await self._redis.delete(key)
            return result > 0
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Redis DELETE failed", e, {'key': key})
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        if not self._redis:
            return False
        
        try:
            return await self._redis.exists(key) > 0
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Redis EXISTS failed", e, {'key': key})
            return False
    
    async def ttl(self, key: str) -> int:
        """Get time to live for a key"""
        if not self._redis:
            return -1
        
        try:
            return await self._redis.ttl(key)
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Redis TTL failed", e, {'key': key})
            return -1
    
    async def get_pipeline(self):
        """Get Redis pipeline for batch operations"""
        if not self._redis:
            return None
        
        return self._redis.pipeline()
    
    @asynccontextmanager
    async def pipeline(self):
        """Context manager for Redis pipeline"""
        if not self._redis:
            yield None
            return
        
        pipe = self._redis.pipeline()
        try:
            yield pipe
            await pipe.execute()
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Redis pipeline failed", e)
            raise
    
    async def health_check(self) -> dict:
        """Perform Redis health check"""
        if not self._redis:
            return {
                'status': 'disconnected',
                'error': 'Redis client not initialized'
            }
        
        try:
            start_time = time.time()
            await self._redis.ping()
            response_time = (time.time() - start_time) * 1000
            
            # Get Redis info
            info = await self._redis.info('server')
            
            return {
                'status': 'healthy',
                'response_time_ms': round(response_time, 2),
                'redis_version': info.get('redis_version', 'unknown'),
                'connected_clients': info.get('connected_clients', 0),
                'used_memory_human': info.get('used_memory_human', 'unknown')
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e)
            }

# Global Redis client instance
redis_client = RedisClient()

import time