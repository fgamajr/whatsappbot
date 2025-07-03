from celery import Celery
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def create_celery_app() -> Celery:
    """Create and configure Celery application"""
    
    celery_app = Celery("whatsapp_interview_bot")
    
    # Configure Celery with settings
    celery_app.conf.update(
        broker_url=settings.CELERY_BROKER_URL,
        result_backend=settings.CELERY_RESULT_BACKEND,
        task_serializer=settings.CELERY_TASK_SERIALIZER,
        result_serializer=settings.CELERY_RESULT_SERIALIZER,
        accept_content=settings.CELERY_ACCEPT_CONTENT,
        timezone=settings.CELERY_TIMEZONE,
        enable_utc=settings.CELERY_ENABLE_UTC,
        
        # Task configuration
        task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
        task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
        task_acks_late=settings.CELERY_TASK_ACKS_LATE,
        task_reject_on_worker_lost=settings.CELERY_TASK_REJECT_ON_WORKER_LOST,
        worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
        
        # Beat schedule
        beat_schedule=settings.CELERY_BEAT_SCHEDULE,
        
        # Import modules with tasks
        include=[
            'app.tasks.audio_processing',
            'app.tasks.audio_pipeline',
            'app.tasks.pipeline_orchestrator',
            'app.tasks.document_generation', 
            'app.tasks.recovery',
            'app.tasks.maintenance',
        ],
        
        # Broker configuration
        broker_transport_options={
            'visibility_timeout': 3600,  # 1 hour visibility timeout
            'fanout_prefix': True,
            'fanout_patterns': True
        },
        
        # Result backend configuration
        result_backend_transport_options={
            'master_name': 'mymaster',
            'retry_on_timeout': True,
        },
        
        # Worker configuration
        worker_send_task_events=True,
        task_send_sent_event=True,
        
        # Monitoring
        task_track_started=True,
        task_publish_retry=True,
        task_publish_retry_policy={
            'max_retries': 3,
            'interval_start': 0,
            'interval_step': 0.2,
            'interval_max': 0.2,
        }
    )
    
    # Task routing for different queues
    celery_app.conf.task_routes = {
        'app.tasks.audio_processing.*': {'queue': 'audio_processing'},
        'app.tasks.document_generation.*': {'queue': 'document_generation'},
        'app.tasks.recovery.*': {'queue': 'maintenance'},
        'app.tasks.maintenance.*': {'queue': 'maintenance'},
    }
    
    # Define queues
    from kombu import Queue
    celery_app.conf.task_queues = (
        Queue('default'),
        Queue('audio_processing'),
        Queue('document_generation'), 
        Queue('maintenance'),
        Queue('high_priority'),
    )
    
    celery_app.conf.task_default_queue = 'default'
    
    logger.info("Celery app configured successfully")
    
    return celery_app

# Create the Celery app instance
celery_app = create_celery_app()

# Celery signal handlers for monitoring
from celery.signals import task_prerun, task_postrun, task_failure, task_retry
from app.utils.secure_logging import SecureLogger

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Handle task pre-execution"""
    SecureLogger.safe_log_info(logger, f"Task {task.name} started", {
        'task_id': task_id,
        'task_name': task.name,
        'args_count': len(args) if args else 0,
        'kwargs_keys': list(kwargs.keys()) if kwargs else []
    })

@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, 
                        retval=None, state=None, **kwds):
    """Handle task post-execution"""
    SecureLogger.safe_log_info(logger, f"Task {task.name} completed", {
        'task_id': task_id,
        'task_name': task.name,
        'state': state,
        'has_retval': retval is not None
    })

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """Handle task failure"""
    SecureLogger.safe_log_error(logger, f"Task {sender.name} failed", exception, {
        'task_id': task_id,
        'task_name': sender.name,
        'exception_type': type(exception).__name__
    })

@task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, einfo=None, **kwds):
    """Handle task retry"""
    SecureLogger.safe_log_warning(logger, f"Task {sender.name} retry", {
        'task_id': task_id,
        'task_name': sender.name,
        'reason': str(reason),
        'retry_count': getattr(sender.request, 'retries', 0)
    })

# Auto-discover tasks from app modules
celery_app.autodiscover_tasks(['app.tasks'], force=True)