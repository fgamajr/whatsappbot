import time
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import logging
import redis.asyncio as redis
from app.infrastructure.redis_client import redis_client
from app.celery_app import celery_app
from app.utils.secure_logging import SecureLogger
from app.infrastructure.prometheus_metrics import prometheus_metrics

logger = logging.getLogger(__name__)

@dataclass
class QueueMetrics:
    """Metrics for a specific Celery queue"""
    name: str
    length: int = 0
    workers_active: int = 0
    workers_total: int = 0
    tasks_processing: int = 0
    avg_processing_time: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
@dataclass 
class WorkerMetrics:
    """Metrics for individual workers"""
    worker_id: str
    hostname: str
    status: str = "unknown"  # online, offline, busy
    active_tasks: int = 0
    processed_tasks: int = 0
    failed_tasks: int = 0
    load_average: float = 0.0
    memory_usage: float = 0.0
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)

@dataclass
class SystemMetrics:
    """Overall system performance metrics"""
    total_workers: int = 0
    total_active_tasks: int = 0
    total_queued_tasks: int = 0
    avg_response_time: float = 0.0
    throughput_per_minute: float = 0.0
    error_rate: float = 0.0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

class MetricsCollector:
    """Advanced metrics collection for Celery system"""
    
    def __init__(self):
        self.queue_metrics: Dict[str, QueueMetrics] = {}
        self.worker_metrics: Dict[str, WorkerMetrics] = {}
        self.system_metrics_history: deque = deque(maxlen=1000)  # Keep last 1000 data points
        self.processing_times: deque = deque(maxlen=100)  # Last 100 task processing times
        self.collection_interval = 30  # seconds
        self.running = False
        
    async def start_collection(self):
        """Start continuous metrics collection"""
        self.running = True
        SecureLogger.safe_log_info(logger, "Starting metrics collection", {
            'collection_interval': self.collection_interval
        })
        
        while self.running:
            try:
                await self.collect_all_metrics()
                await asyncio.sleep(self.collection_interval)
            except Exception as e:
                SecureLogger.safe_log_error(logger, "Metrics collection error", e)
                await asyncio.sleep(5)  # Short delay before retry
    
    def stop_collection(self):
        """Stop metrics collection"""
        self.running = False
        SecureLogger.safe_log_info(logger, "Metrics collection stopped")
    
    async def collect_all_metrics(self):
        """Collect all types of metrics"""
        try:
            # Collect in parallel for better performance
            await asyncio.gather(
                self.collect_queue_metrics(),
                self.collect_worker_metrics(),
                self.collect_system_metrics(),
                return_exceptions=True
            )
            
            # Store metrics in Redis for persistence
            await self.store_metrics_in_redis()
            
            # Update Prometheus metrics
            current_metrics = self.get_current_metrics()
            prometheus_metrics.collect_all_metrics(current_metrics)
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to collect metrics", e)
    
    async def collect_queue_metrics(self):
        """Collect metrics for all Celery queues"""
        try:
            inspect = celery_app.control.inspect()
            
            # Get active queues from all workers
            active_queues = inspect.active_queues() or {}
            reserved_tasks = inspect.reserved() or {}
            active_tasks = inspect.active() or {}
            
            # Queue names from configuration
            queue_names = ['default', 'audio_processing', 'document_generation', 'maintenance', 'high_priority']
            
            for queue_name in queue_names:
                # Count tasks in queue using Redis
                queue_length = await self.get_redis_queue_length(queue_name)
                
                # Count workers processing this queue
                workers_for_queue = 0
                tasks_processing = 0
                
                for worker_name, queues in active_queues.items():
                    if any(q['name'] == queue_name for q in queues):
                        workers_for_queue += 1
                
                # Count active tasks for this queue
                for worker_name, tasks in active_tasks.items():
                    for task in tasks:
                        if task.get('routing_key', '').startswith(queue_name):
                            tasks_processing += 1
                
                # Calculate average processing time (simplified)
                avg_time = self.calculate_avg_processing_time(queue_name)
                
                self.queue_metrics[queue_name] = QueueMetrics(
                    name=queue_name,
                    length=queue_length,
                    workers_active=workers_for_queue,
                    tasks_processing=tasks_processing,
                    avg_processing_time=avg_time,
                    last_updated=datetime.utcnow()
                )
            
            SecureLogger.safe_log_info(logger, "Queue metrics collected", {
                'queues_monitored': len(queue_names),
                'total_queued_tasks': sum(m.length for m in self.queue_metrics.values())
            })
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to collect queue metrics", e)
    
    async def collect_worker_metrics(self):
        """Collect metrics for all Celery workers"""
        try:
            inspect = celery_app.control.inspect()
            
            # Get worker statistics
            stats = inspect.stats() or {}
            active_tasks = inspect.active() or {}
            
            for worker_name, worker_stats in stats.items():
                # Extract worker information
                hostname = worker_stats.get('hostname', worker_name)
                
                # Count active tasks for this worker
                active_count = len(active_tasks.get(worker_name, []))
                
                # Get processed/failed counts from stats
                total_processed = worker_stats.get('total', {}).get('total', 0)
                
                # Extract system info if available
                load_avg = 0.0
                memory_usage = 0.0
                
                if 'rusage' in worker_stats:
                    # System resource usage
                    load_avg = worker_stats['rusage'].get('stime', 0.0)
                    memory_usage = worker_stats['rusage'].get('maxrss', 0.0) / 1024 / 1024  # Convert to MB
                
                # Determine worker status
                status = "online" if worker_name in stats else "offline"
                if active_count > 0:
                    status = "busy"
                
                self.worker_metrics[worker_name] = WorkerMetrics(
                    worker_id=worker_name,
                    hostname=hostname,
                    status=status,
                    active_tasks=active_count,
                    processed_tasks=total_processed,
                    load_average=load_avg,
                    memory_usage=memory_usage,
                    last_heartbeat=datetime.utcnow()
                )
            
            SecureLogger.safe_log_info(logger, "Worker metrics collected", {
                'workers_monitored': len(self.worker_metrics),
                'workers_online': len([w for w in self.worker_metrics.values() if w.status != "offline"])
            })
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to collect worker metrics", e)
    
    async def collect_system_metrics(self):
        """Collect overall system metrics"""
        try:
            # Calculate system-wide metrics
            total_workers = len(self.worker_metrics)
            total_active_tasks = sum(w.active_tasks for w in self.worker_metrics.values())
            total_queued_tasks = sum(q.length for q in self.queue_metrics.values())
            
            # Calculate throughput (tasks per minute)
            throughput = self.calculate_throughput()
            
            # Calculate error rate
            error_rate = self.calculate_error_rate()
            
            # Calculate average response time
            avg_response_time = sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0.0
            
            # System resource usage (averaged across workers)
            cpu_usage = sum(w.load_average for w in self.worker_metrics.values()) / total_workers if total_workers > 0 else 0.0
            memory_usage = sum(w.memory_usage for w in self.worker_metrics.values()) / total_workers if total_workers > 0 else 0.0
            
            system_metrics = SystemMetrics(
                total_workers=total_workers,
                total_active_tasks=total_active_tasks,
                total_queued_tasks=total_queued_tasks,
                avg_response_time=avg_response_time,
                throughput_per_minute=throughput,
                error_rate=error_rate,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                timestamp=datetime.utcnow()
            )
            
            # Store in history
            self.system_metrics_history.append(system_metrics)
            
            SecureLogger.safe_log_info(logger, "System metrics collected", {
                'total_workers': total_workers,
                'total_active_tasks': total_active_tasks,
                'total_queued_tasks': total_queued_tasks,
                'throughput_per_minute': throughput
            })
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to collect system metrics", e)
    
    async def get_redis_queue_length(self, queue_name: str) -> int:
        """Get queue length from Redis"""
        try:
            if not await redis_client.is_connected():
                return 0
            
            # Celery uses different Redis DB for broker
            broker_redis = redis.from_url("redis://localhost:6379/1", decode_responses=True)
            queue_length = await broker_redis.llen(queue_name)
            await broker_redis.aclose()
            
            return queue_length
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to get queue length", e, {
                'queue_name': queue_name
            })
            return 0
    
    def calculate_avg_processing_time(self, queue_name: str) -> float:
        """Calculate average processing time for a queue"""
        # This is a simplified calculation
        # In practice, you'd track task start/end times per queue
        if not self.processing_times:
            return 0.0
        
        return sum(self.processing_times) / len(self.processing_times)
    
    def calculate_throughput(self) -> float:
        """Calculate tasks processed per minute"""
        if len(self.system_metrics_history) < 2:
            return 0.0
        
        # Get metrics from 1 minute ago
        now = datetime.utcnow()
        one_minute_ago = now - timedelta(minutes=1)
        
        recent_metrics = [m for m in self.system_metrics_history if m.timestamp > one_minute_ago]
        
        if len(recent_metrics) < 2:
            return 0.0
        
        # Calculate task completion rate
        oldest = recent_metrics[0]
        newest = recent_metrics[-1]
        
        # This is simplified - you'd track actual completions
        return max(0, newest.total_active_tasks - oldest.total_active_tasks)
    
    def calculate_error_rate(self) -> float:
        """Calculate current error rate"""
        # Simplified error rate calculation
        # In practice, you'd track failed vs successful tasks
        total_workers = len(self.worker_metrics)
        if total_workers == 0:
            return 0.0
        
        # Assume error rate based on worker failures (simplified)
        offline_workers = len([w for w in self.worker_metrics.values() if w.status == "offline"])
        
        return (offline_workers / total_workers) * 100
    
    async def store_metrics_in_redis(self):
        """Store current metrics in Redis for persistence"""
        try:
            if not await redis_client.is_connected():
                return
            
            # Store latest metrics
            metrics_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'queues': {name: {
                    'length': m.length,
                    'workers_active': m.workers_active,
                    'tasks_processing': m.tasks_processing,
                    'avg_processing_time': m.avg_processing_time
                } for name, m in self.queue_metrics.items()},
                'workers': {name: {
                    'status': m.status,
                    'active_tasks': m.active_tasks,
                    'processed_tasks': m.processed_tasks,
                    'load_average': m.load_average,
                    'memory_usage': m.memory_usage
                } for name, m in self.worker_metrics.items()},
                'system': {
                    'total_workers': self.system_metrics_history[-1].total_workers if self.system_metrics_history else 0,
                    'total_active_tasks': self.system_metrics_history[-1].total_active_tasks if self.system_metrics_history else 0,
                    'total_queued_tasks': self.system_metrics_history[-1].total_queued_tasks if self.system_metrics_history else 0,
                    'throughput_per_minute': self.system_metrics_history[-1].throughput_per_minute if self.system_metrics_history else 0,
                    'error_rate': self.system_metrics_history[-1].error_rate if self.system_metrics_history else 0
                }
            }
            
            # Store with expiration
            await redis_client.set(
                'celery:metrics:latest',
                str(metrics_data),
                expire=300  # 5 minutes expiration
            )
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to store metrics in Redis", e)
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot"""
        return {
            'queues': {name: {
                'length': m.length,
                'workers_active': m.workers_active,
                'tasks_processing': m.tasks_processing,
                'avg_processing_time': m.avg_processing_time,
                'last_updated': m.last_updated.isoformat()
            } for name, m in self.queue_metrics.items()},
            'workers': {name: {
                'status': m.status,
                'active_tasks': m.active_tasks,
                'processed_tasks': m.processed_tasks,
                'load_average': m.load_average,
                'memory_usage': m.memory_usage,
                'last_heartbeat': m.last_heartbeat.isoformat()
            } for name, m in self.worker_metrics.items()},
            'system': {
                'total_workers': self.system_metrics_history[-1].total_workers if self.system_metrics_history else 0,
                'total_active_tasks': self.system_metrics_history[-1].total_active_tasks if self.system_metrics_history else 0,
                'total_queued_tasks': self.system_metrics_history[-1].total_queued_tasks if self.system_metrics_history else 0,
                'avg_response_time': self.system_metrics_history[-1].avg_response_time if self.system_metrics_history else 0,
                'throughput_per_minute': self.system_metrics_history[-1].throughput_per_minute if self.system_metrics_history else 0,
                'error_rate': self.system_metrics_history[-1].error_rate if self.system_metrics_history else 0,
                'cpu_usage': self.system_metrics_history[-1].cpu_usage if self.system_metrics_history else 0,
                'memory_usage': self.system_metrics_history[-1].memory_usage if self.system_metrics_history else 0,
                'timestamp': self.system_metrics_history[-1].timestamp.isoformat() if self.system_metrics_history else datetime.utcnow().isoformat()
            },
            'collection_active': self.running
        }
    
    def record_task_completion(self, task_id: str, processing_time: float):
        """Record task completion for metrics"""
        self.processing_times.append(processing_time)
        
        SecureLogger.safe_log_info(logger, "Task completion recorded", {
            'task_id': task_id,
            'processing_time': processing_time
        })

# Global metrics collector instance
metrics_collector = MetricsCollector()