from celery import shared_task
from typing import Dict, Any
import logging
from app.utils.secure_logging import SecureLogger

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    name='maintenance.database_cleanup'
)
def database_cleanup_task(self, max_age_days: int = 30):
    """
    Clean up old database records
    
    Args:
        max_age_days: Maximum age in days for records to keep
    """
    try:
        SecureLogger.safe_log_info(logger, "Starting database cleanup", {
            'task_id': self.request.id,
            'max_age_days': max_age_days
        })
        
        # Import here to avoid circular imports
        from app.infrastructure.database.mongodb import MongoDB
        from datetime import datetime, timedelta
        
        # Create new event loop for async operations
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
            
            db = loop.run_until_complete(MongoDB.get_database())
            
            # Clean up old interviews (completed or failed)
            interviews_result = loop.run_until_complete(
                db.interviews.delete_many({
                    'created_at': {'$lt': cutoff_date},
                    'status': {'$in': ['completed', 'failed', 'cancelled']}
                })
            )
            
            # Clean up orphaned temporary files metadata
            # (actual files should be cleaned by file cleanup tasks)
            temp_files_result = loop.run_until_complete(
                db.temp_files.delete_many({
                    'created_at': {'$lt': cutoff_date}
                })
            )
            
            SecureLogger.safe_log_info(logger, "Database cleanup completed", {
                'task_id': self.request.id,
                'interviews_deleted': interviews_result.deleted_count,
                'temp_files_deleted': temp_files_result.deleted_count,
                'cutoff_date': cutoff_date.isoformat()
            })
            
            return {
                'status': 'success',
                'interviews_deleted': interviews_result.deleted_count,
                'temp_files_deleted': temp_files_result.deleted_count,
                'cutoff_date': cutoff_date.isoformat(),
                'task_id': self.request.id
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Database cleanup failed", e, {
            'task_id': self.request.id,
            'max_age_days': max_age_days
        })
        
        return {
            'status': 'failed',
            'error': str(e),
            'task_id': self.request.id
        }

@shared_task(
    bind=True,
    name='maintenance.redis_memory_check'
)
def redis_memory_check_task(self):
    """
    Check Redis memory usage and log warnings if high
    """
    try:
        SecureLogger.safe_log_info(logger, "Starting Redis memory check", {
            'task_id': self.request.id
        })
        
        # Import here to avoid circular imports
        from app.infrastructure.redis_client import redis_client
        
        # Create new event loop for async operations
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            if not loop.run_until_complete(redis_client.is_connected()):
                SecureLogger.safe_log_warning(logger, "Redis not connected during memory check", {
                    'task_id': self.request.id
                })
                return {
                    'status': 'warning',
                    'message': 'Redis not connected',
                    'task_id': self.request.id
                }
            
            # Get Redis info
            info = loop.run_until_complete(redis_client._redis.info('memory'))
            
            used_memory = info.get('used_memory', 0)
            used_memory_human = info.get('used_memory_human', 'unknown')
            max_memory = info.get('maxmemory', 0)
            
            # Calculate memory usage percentage
            memory_usage_pct = 0
            if max_memory > 0:
                memory_usage_pct = (used_memory / max_memory) * 100
            
            # Log warning if memory usage is high
            if memory_usage_pct > 80:
                SecureLogger.safe_log_warning(logger, "High Redis memory usage detected", {
                    'task_id': self.request.id,
                    'memory_usage_pct': memory_usage_pct,
                    'used_memory_human': used_memory_human,
                    'used_memory_bytes': used_memory,
                    'max_memory_bytes': max_memory
                })
            
            SecureLogger.safe_log_info(logger, "Redis memory check completed", {
                'task_id': self.request.id,
                'memory_usage_pct': memory_usage_pct,
                'used_memory_human': used_memory_human
            })
            
            return {
                'status': 'success',
                'memory_usage_pct': memory_usage_pct,
                'used_memory_human': used_memory_human,
                'used_memory_bytes': used_memory,
                'max_memory_bytes': max_memory,
                'task_id': self.request.id
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Redis memory check failed", e, {
            'task_id': self.request.id
        })
        
        return {
            'status': 'failed',
            'error': str(e),
            'task_id': self.request.id
        }

@shared_task(
    bind=True,
    name='maintenance.health_check'
)
def health_check_task(self):
    """
    Comprehensive system health check
    """
    try:
        SecureLogger.safe_log_info(logger, "Starting system health check", {
            'task_id': self.request.id
        })
        
        health_status = {
            'mongodb': 'unknown',
            'redis': 'unknown', 
            'celery_broker': 'unknown',
            'overall': 'unknown'
        }
        
        # Create new event loop for async operations
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Check MongoDB
            try:
                from app.infrastructure.database.mongodb import MongoDB
                db = loop.run_until_complete(MongoDB.get_database())
                loop.run_until_complete(db.command("ping"))
                health_status['mongodb'] = 'healthy'
            except Exception:
                health_status['mongodb'] = 'unhealthy'
            
            # Check Redis
            try:
                from app.infrastructure.redis_client import redis_client
                if loop.run_until_complete(redis_client.is_connected()):
                    health_status['redis'] = 'healthy'
                else:
                    health_status['redis'] = 'unhealthy'
            except Exception:
                health_status['redis'] = 'unhealthy'
            
            # Check Celery broker (Redis on different DB)
            try:
                from app.celery_app import celery_app
                inspect = celery_app.control.inspect()
                stats = inspect.stats()
                if stats:
                    health_status['celery_broker'] = 'healthy'
                else:
                    health_status['celery_broker'] = 'unhealthy'
            except Exception:
                health_status['celery_broker'] = 'unhealthy'
            
            # Overall health
            unhealthy_services = [k for k, v in health_status.items() 
                                if v == 'unhealthy' and k != 'overall']
            
            if not unhealthy_services:
                health_status['overall'] = 'healthy'
            elif len(unhealthy_services) == 1:
                health_status['overall'] = 'degraded'
            else:
                health_status['overall'] = 'unhealthy'
            
        finally:
            loop.close()
        
        SecureLogger.safe_log_info(logger, "System health check completed", {
            'task_id': self.request.id,
            'health_status': health_status
        })
        
        return {
            'status': 'success',
            'health_status': health_status,
            'task_id': self.request.id
        }
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "System health check failed", e, {
            'task_id': self.request.id
        })
        
        return {
            'status': 'failed',
            'error': str(e),
            'task_id': self.request.id
        }