import time
import logging
from typing import Dict, Any, Optional
from prometheus_client import Counter, Histogram, Gauge, Summary, start_http_server
from functools import wraps
from app.utils.secure_logging import SecureLogger

logger = logging.getLogger(__name__)

class PrometheusMetrics:
    """Prometheus metrics collection for Celery system"""
    
    def __init__(self):
        # Task metrics
        self.task_counter = Counter(
            'celery_tasks_total',
            'Total number of Celery tasks',
            ['task_name', 'queue', 'status']
        )
        
        self.task_duration = Histogram(
            'celery_task_duration_seconds',
            'Task execution duration',
            ['task_name', 'queue'],
            buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0]
        )
        
        self.task_retry_counter = Counter(
            'celery_task_retries_total',
            'Total number of task retries',
            ['task_name', 'queue', 'retry_reason']
        )
        
        # Queue metrics
        self.queue_length = Gauge(
            'celery_queue_length',
            'Current queue length',
            ['queue_name']
        )
        
        self.queue_processing_time = Summary(
            'celery_queue_processing_seconds',
            'Time spent processing queue tasks',
            ['queue_name']
        )
        
        # Worker metrics
        self.worker_active_tasks = Gauge(
            'celery_worker_active_tasks',
            'Number of active tasks per worker',
            ['worker_name', 'hostname']
        )
        
        self.worker_processed_tasks = Counter(
            'celery_worker_processed_tasks_total',
            'Total tasks processed by worker',
            ['worker_name', 'hostname']
        )
        
        self.worker_memory_usage = Gauge(
            'celery_worker_memory_usage_bytes',
            'Worker memory usage in bytes',
            ['worker_name', 'hostname']
        )
        
        self.worker_cpu_usage = Gauge(
            'celery_worker_cpu_usage_percent',
            'Worker CPU usage percentage',
            ['worker_name', 'hostname']
        )
        
        # System metrics
        self.system_total_workers = Gauge(
            'celery_system_total_workers',
            'Total number of active workers'
        )
        
        self.system_total_queued_tasks = Gauge(
            'celery_system_total_queued_tasks',
            'Total number of queued tasks across all queues'
        )
        
        self.system_throughput = Gauge(
            'celery_system_throughput_per_minute',
            'System throughput in tasks per minute'
        )
        
        self.system_error_rate = Gauge(
            'celery_system_error_rate_percent',
            'System error rate percentage'
        )
        
        # Pipeline metrics
        self.pipeline_duration = Histogram(
            'celery_pipeline_duration_seconds',
            'Complete pipeline execution duration',
            ['pipeline_type'],
            buckets=[60.0, 300.0, 600.0, 900.0, 1200.0, 1800.0, 3600.0]
        )
        
        self.pipeline_success_rate = Gauge(
            'celery_pipeline_success_rate_percent',
            'Pipeline success rate percentage',
            ['pipeline_type']
        )
        
        # Auto-scaling metrics
        self.autoscaling_decisions = Counter(
            'celery_autoscaling_decisions_total',
            'Total auto-scaling decisions',
            ['queue_name', 'action', 'reason']
        )
        
        self.autoscaling_workers = Gauge(
            'celery_autoscaling_target_workers',
            'Target number of workers from auto-scaling',
            ['queue_name']
        )
        
        # WebSocket metrics
        self.websocket_connections = Gauge(
            'websocket_active_connections',
            'Number of active WebSocket connections',
            ['connection_type']
        )
        
        self.websocket_messages_sent = Counter(
            'websocket_messages_sent_total',
            'Total WebSocket messages sent',
            ['message_type', 'connection_type']
        )
        
        self.http_server_started = False
        
    def start_metrics_server(self, port: int = 8001):
        """Start Prometheus metrics HTTP server"""
        if not self.http_server_started:
            try:
                start_http_server(port)
                self.http_server_started = True
                SecureLogger.safe_log_info(logger, "Prometheus metrics server started", {
                    'port': port,
                    'endpoint': f'http://localhost:{port}/metrics'
                })
            except Exception as e:
                SecureLogger.safe_log_error(logger, "Failed to start Prometheus metrics server", e)
    
    def record_task_start(self, task_name: str, queue: str):
        """Record task start"""
        self.task_counter.labels(task_name=task_name, queue=queue, status='started').inc()
    
    def record_task_completion(self, task_name: str, queue: str, duration: float, success: bool):
        """Record task completion"""
        status = 'success' if success else 'failure'
        self.task_counter.labels(task_name=task_name, queue=queue, status=status).inc()
        self.task_duration.labels(task_name=task_name, queue=queue).observe(duration)
    
    def record_task_retry(self, task_name: str, queue: str, reason: str):
        """Record task retry"""
        self.task_retry_counter.labels(task_name=task_name, queue=queue, retry_reason=reason).inc()
    
    def update_queue_metrics(self, queue_name: str, length: int, processing_time: Optional[float] = None):
        """Update queue metrics"""
        self.queue_length.labels(queue_name=queue_name).set(length)
        if processing_time:
            self.queue_processing_time.labels(queue_name=queue_name).observe(processing_time)
    
    def update_worker_metrics(self, worker_name: str, hostname: str, active_tasks: int, 
                             processed_tasks: int, memory_usage: float, cpu_usage: float):
        """Update worker metrics"""
        self.worker_active_tasks.labels(worker_name=worker_name, hostname=hostname).set(active_tasks)
        self.worker_processed_tasks.labels(worker_name=worker_name, hostname=hostname).inc(processed_tasks)
        self.worker_memory_usage.labels(worker_name=worker_name, hostname=hostname).set(memory_usage)
        self.worker_cpu_usage.labels(worker_name=worker_name, hostname=hostname).set(cpu_usage)
    
    def update_system_metrics(self, total_workers: int, total_queued_tasks: int, 
                             throughput: float, error_rate: float):
        """Update system-wide metrics"""
        self.system_total_workers.set(total_workers)
        self.system_total_queued_tasks.set(total_queued_tasks)
        self.system_throughput.set(throughput)
        self.system_error_rate.set(error_rate)
    
    def record_pipeline_completion(self, pipeline_type: str, duration: float, success: bool):
        """Record pipeline completion"""
        self.pipeline_duration.labels(pipeline_type=pipeline_type).observe(duration)
        # Update success rate (simplified - in practice you'd track over time)
        success_rate = 100.0 if success else 0.0
        self.pipeline_success_rate.labels(pipeline_type=pipeline_type).set(success_rate)
    
    def record_scaling_decision(self, queue_name: str, action: str, reason: str, target_workers: int):
        """Record auto-scaling decision"""
        self.autoscaling_decisions.labels(queue_name=queue_name, action=action, reason=reason).inc()
        self.autoscaling_workers.labels(queue_name=queue_name).set(target_workers)
    
    def update_websocket_metrics(self, connection_type: str, active_connections: int):
        """Update WebSocket metrics"""
        self.websocket_connections.labels(connection_type=connection_type).set(active_connections)
    
    def record_websocket_message(self, message_type: str, connection_type: str):
        """Record WebSocket message sent"""
        self.websocket_messages_sent.labels(message_type=message_type, connection_type=connection_type).inc()
    
    def collect_all_metrics(self, metrics_data: Dict[str, Any]):
        """Collect all metrics from metrics collector"""
        try:
            # Update queue metrics
            for queue_name, queue_data in metrics_data.get('queues', {}).items():
                self.update_queue_metrics(
                    queue_name=queue_name,
                    length=queue_data.get('length', 0),
                    processing_time=queue_data.get('avg_processing_time', 0)
                )
            
            # Update worker metrics
            for worker_name, worker_data in metrics_data.get('workers', {}).items():
                hostname = worker_data.get('hostname', worker_name)
                self.update_worker_metrics(
                    worker_name=worker_name,
                    hostname=hostname,
                    active_tasks=worker_data.get('active_tasks', 0),
                    processed_tasks=worker_data.get('processed_tasks', 0),
                    memory_usage=worker_data.get('memory_usage', 0.0) * 1024 * 1024,  # Convert to bytes
                    cpu_usage=worker_data.get('load_average', 0.0)
                )
            
            # Update system metrics
            system_data = metrics_data.get('system', {})
            self.update_system_metrics(
                total_workers=system_data.get('total_workers', 0),
                total_queued_tasks=system_data.get('total_queued_tasks', 0),
                throughput=system_data.get('throughput_per_minute', 0.0),
                error_rate=system_data.get('error_rate', 0.0)
            )
            
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to collect Prometheus metrics", e)

def prometheus_task_metrics(func):
    """Decorator to automatically collect task metrics"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        task_name = func.__name__
        queue = getattr(func, 'queue', 'default')
        
        # Record task start
        prometheus_metrics.record_task_start(task_name, queue)
        
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            prometheus_metrics.record_task_completion(task_name, queue, duration, True)
            return result
        except Exception as e:
            duration = time.time() - start_time
            prometheus_metrics.record_task_completion(task_name, queue, duration, False)
            raise
    
    return wrapper

def prometheus_pipeline_metrics(pipeline_type: str):
    """Decorator to collect pipeline metrics"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                prometheus_metrics.record_pipeline_completion(pipeline_type, duration, True)
                return result
            except Exception as e:
                duration = time.time() - start_time
                prometheus_metrics.record_pipeline_completion(pipeline_type, duration, False)
                raise
        return wrapper
    return decorator

# Global Prometheus metrics instance
prometheus_metrics = PrometheusMetrics()