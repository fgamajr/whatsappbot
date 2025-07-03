from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
from app.tasks.audio_processing import test_audio_task, process_audio_message_task
from app.tasks.document_generation import cleanup_temp_files_task
from app.tasks.maintenance import health_check_task, redis_memory_check_task
from app.tasks.pipeline_orchestrator import start_audio_processing, start_express_processing, get_pipeline_status
from celery.result import AsyncResult
from app.celery_app import celery_app
from app.utils.secure_logging import SecureLogger
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

class TaskRequest(BaseModel):
    x: int
    y: int

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@router.post("/test", response_model=TaskResponse)
async def test_celery_task(request: TaskRequest):
    """Test Celery with a simple addition task"""
    try:
        task = test_audio_task.delay(request.x, request.y)
        
        SecureLogger.safe_log_info(logger, "Test Celery task started", {
            'task_id': task.id,
            'x': request.x,
            'y': request.y
        })
        
        return TaskResponse(
            task_id=task.id,
            status="pending",
            message=f"Test task started: {request.x} + {request.y}"
        )
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to start test task", e)
        raise HTTPException(status_code=500, detail=f"Failed to start task: {str(e)}")

@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """Get the status of a Celery task"""
    try:
        task_result = AsyncResult(task_id, app=celery_app)
        
        response = TaskStatusResponse(
            task_id=task_id,
            status=task_result.status
        )
        
        if task_result.ready():
            if task_result.successful():
                response.result = task_result.result
            else:
                response.error = str(task_result.info)
        
        return response
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to get task status", e, {
            'task_id': task_id
        })
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")

@router.post("/health-check")
async def trigger_health_check():
    """Trigger a comprehensive system health check"""
    try:
        task = health_check_task.delay()
        
        SecureLogger.safe_log_info(logger, "Health check task started", {
            'task_id': task.id
        })
        
        return TaskResponse(
            task_id=task.id,
            status="pending",
            message="System health check started"
        )
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to start health check", e)
        raise HTTPException(status_code=500, detail=f"Failed to start health check: {str(e)}")

@router.post("/redis-memory-check")
async def trigger_redis_memory_check():
    """Trigger Redis memory usage check"""
    try:
        task = redis_memory_check_task.delay()
        
        SecureLogger.safe_log_info(logger, "Redis memory check task started", {
            'task_id': task.id
        })
        
        return TaskResponse(
            task_id=task.id,
            status="pending",
            message="Redis memory check started"
        )
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to start Redis memory check", e)
        raise HTTPException(status_code=500, detail=f"Failed to start Redis memory check: {str(e)}")

@router.get("/worker-stats")
async def get_worker_stats():
    """Get Celery worker statistics"""
    try:
        inspect = celery_app.control.inspect()
        
        stats = {
            'active_tasks': inspect.active(),
            'scheduled_tasks': inspect.scheduled(),
            'worker_stats': inspect.stats(),
            'registered_tasks': inspect.registered()
        }
        
        SecureLogger.safe_log_info(logger, "Worker stats retrieved", {
            'active_workers': len(stats['worker_stats'] or {}),
            'total_active_tasks': sum(len(tasks) for tasks in (stats['active_tasks'] or {}).values())
        })
        
        return stats
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to get worker stats", e)
        raise HTTPException(status_code=500, detail=f"Failed to get worker stats: {str(e)}")

@router.post("/cleanup-files")
async def trigger_file_cleanup(file_paths: list):
    """Trigger file cleanup task"""
    try:
        if not file_paths:
            raise HTTPException(status_code=400, detail="No file paths provided")
        
        task = cleanup_temp_files_task.delay(file_paths)
        
        SecureLogger.safe_log_info(logger, "File cleanup task started", {
            'task_id': task.id,
            'file_count': len(file_paths)
        })
        
        return TaskResponse(
            task_id=task.id,
            status="pending",
            message=f"File cleanup started for {len(file_paths)} files"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to start file cleanup", e)
        raise HTTPException(status_code=500, detail=f"Failed to start file cleanup: {str(e)}")

@router.get("/queue-info")
async def get_queue_info():
    """Get information about Celery queues"""
    try:
        inspect = celery_app.control.inspect()
        
        # Get active queues
        active_queues = inspect.active_queues()
        
        # Get queue lengths (this requires additional setup)
        queue_info = {
            'active_queues': active_queues,
            'queue_names': ['default', 'audio_processing', 'document_generation', 'maintenance', 'high_priority']
        }
        
        SecureLogger.safe_log_info(logger, "Queue info retrieved", {
            'active_workers': len(active_queues or {}),
            'configured_queues': len(queue_info['queue_names'])
        })
        
        return queue_info
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to get queue info", e)
        raise HTTPException(status_code=500, detail=f"Failed to get queue info: {str(e)}")

@router.delete("/revoke-task/{task_id}")
async def revoke_task(task_id: str, terminate: bool = False):
    """Revoke (cancel) a Celery task"""
    try:
        celery_app.control.revoke(task_id, terminate=terminate)
        
        SecureLogger.safe_log_info(logger, "Task revoked", {
            'task_id': task_id,
            'terminate': terminate
        })
        
        return {
            'message': f"Task {task_id} has been {'terminated' if terminate else 'revoked'}",
            'task_id': task_id,
            'terminated': terminate
        }
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to revoke task", e, {
            'task_id': task_id
        })
        raise HTTPException(status_code=500, detail=f"Failed to revoke task: {str(e)}")

# ================================
# PIPELINE TESTING ENDPOINTS
# ================================

class AudioMessageTest(BaseModel):
    from_number: str = "+5511999887766"
    message_id: str = "test_msg_123"
    media_id: dict = {
        "audio": {"file_id": "test_audio_file_123"},
        "message_id": "test_msg_123"
    }

@router.post("/test-pipeline")
async def test_audio_pipeline(request: AudioMessageTest):
    """Test the new optimized audio processing pipeline"""
    try:
        message_data = {
            "from": request.from_number,
            "message_id": request.message_id,
            "media_id": request.media_id,
            "type": "audio"
        }
        
        # Start optimized pipeline
        pipeline_id = start_audio_processing(message_data, priority='normal')
        
        SecureLogger.safe_log_info(logger, "Test pipeline started", {
            'pipeline_id': pipeline_id,
            'message_id': request.message_id
        })
        
        return TaskResponse(
            task_id=pipeline_id,
            status="pipeline_started",
            message=f"Optimized audio pipeline started for test message"
        )
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to start test pipeline", e)
        raise HTTPException(status_code=500, detail=f"Failed to start pipeline: {str(e)}")

@router.post("/test-express-pipeline")
async def test_express_pipeline(request: AudioMessageTest):
    """Test the express (high priority) audio processing pipeline"""
    try:
        message_data = {
            "from": request.from_number,
            "message_id": request.message_id,
            "media_id": request.media_id,
            "type": "audio"
        }
        
        # Start express pipeline
        pipeline_id = start_express_processing(message_data)
        
        SecureLogger.safe_log_info(logger, "Test express pipeline started", {
            'pipeline_id': pipeline_id,
            'message_id': request.message_id
        })
        
        return TaskResponse(
            task_id=pipeline_id,
            status="express_pipeline_started",
            message=f"Express audio pipeline started for test message"
        )
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to start test express pipeline", e)
        raise HTTPException(status_code=500, detail=f"Failed to start express pipeline: {str(e)}")

@router.get("/pipeline-status/{pipeline_id}")
async def get_pipeline_status_endpoint(pipeline_id: str):
    """Get detailed status of a running pipeline"""
    try:
        # Get pipeline result
        pipeline_result = AsyncResult(pipeline_id, app=celery_app)
        
        # Get comprehensive status
        status_info = get_pipeline_status(pipeline_result)
        
        SecureLogger.safe_log_info(logger, "Pipeline status retrieved", {
            'pipeline_id': pipeline_id,
            'state': status_info.get('state', 'unknown')
        })
        
        return status_info
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to get pipeline status", e, {
            'pipeline_id': pipeline_id
        })
        raise HTTPException(status_code=500, detail=f"Failed to get pipeline status: {str(e)}")

@router.post("/test-legacy-vs-pipeline")
async def test_legacy_vs_pipeline():
    """Compare legacy vs optimized pipeline performance"""
    try:
        test_message = {
            "from": "+5511999887766",
            "message_id": "performance_test_123",
            "media_id": {
                "audio": {"file_id": "perf_test_audio"},
                "message_id": "performance_test_123"
            },
            "type": "audio"
        }
        
        # Start both pipelines for comparison
        legacy_task = process_audio_message_task.delay(test_message, use_pipeline=False)
        pipeline_task = process_audio_message_task.delay(test_message, use_pipeline=True)
        
        SecureLogger.safe_log_info(logger, "Performance comparison test started", {
            'legacy_task_id': legacy_task.id,
            'pipeline_task_id': pipeline_task.id
        })
        
        return {
            "message": "Performance comparison started",
            "legacy_task_id": legacy_task.id,
            "pipeline_task_id": pipeline_task.id,
            "compare_url": f"/celery/performance-results/{legacy_task.id}/{pipeline_task.id}"
        }
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to start performance comparison", e)
        raise HTTPException(status_code=500, detail=f"Failed to start comparison: {str(e)}")

@router.get("/performance-results/{legacy_id}/{pipeline_id}")
async def get_performance_comparison(legacy_id: str, pipeline_id: str):
    """Get performance comparison results"""
    try:
        legacy_result = AsyncResult(legacy_id, app=celery_app)
        pipeline_result = AsyncResult(pipeline_id, app=celery_app)
        
        comparison = {
            "legacy": {
                "task_id": legacy_id,
                "state": legacy_result.state,
                "ready": legacy_result.ready(),
                "successful": legacy_result.successful() if legacy_result.ready() else None
            },
            "pipeline": {
                "task_id": pipeline_id,
                "state": pipeline_result.state,
                "ready": pipeline_result.ready(),
                "successful": pipeline_result.successful() if pipeline_result.ready() else None
            }
        }
        
        # Add timing information if available
        if legacy_result.ready() and pipeline_result.ready():
            comparison["comparison"] = {
                "both_completed": True,
                "winner": "pipeline" if pipeline_result.successful() else "legacy"
            }
        
        return comparison
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to get performance comparison", e)
        raise HTTPException(status_code=500, detail=f"Failed to get comparison: {str(e)}")

@router.get("/pipeline-config")
async def get_pipeline_config():
    """Get current pipeline configuration"""
    try:
        config = {
            "use_optimized_pipeline": settings.USE_OPTIMIZED_PIPELINE,
            "small_audio_threshold_mb": settings.PIPELINE_SMALL_AUDIO_THRESHOLD_MB,
            "parallel_chunk_limit": settings.PIPELINE_PARALLEL_CHUNK_LIMIT,
            "audio_chunk_minutes": settings.AUDIO_CHUNK_MINUTES,
            "max_retries": settings.CELERY_TASK_MAX_RETRIES,
            "soft_time_limit": settings.CELERY_TASK_SOFT_TIME_LIMIT,
            "time_limit": settings.CELERY_TASK_TIME_LIMIT
        }
        
        return config
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to get pipeline config", e)
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")

@router.post("/toggle-pipeline")
async def toggle_pipeline_mode(enable: bool = True):
    """Toggle between optimized pipeline and legacy processing"""
    try:
        # Note: This would typically update a configuration store
        # For demo purposes, we'll just return the current setting
        
        current_mode = "optimized_pipeline" if settings.USE_OPTIMIZED_PIPELINE else "legacy_processing"
        requested_mode = "optimized_pipeline" if enable else "legacy_processing"
        
        SecureLogger.safe_log_info(logger, "Pipeline mode toggle requested", {
            'current_mode': current_mode,
            'requested_mode': requested_mode,
            'enable': enable
        })
        
        return {
            "message": f"Pipeline mode toggle requested",
            "current_mode": current_mode,
            "requested_mode": requested_mode,
            "note": "In production, this would update the configuration store"
        }
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to toggle pipeline mode", e)
        raise HTTPException(status_code=500, detail=f"Failed to toggle mode: {str(e)}")