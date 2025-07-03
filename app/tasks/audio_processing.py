from celery import shared_task
from typing import Dict, Any
import logging
from app.services.message_handler import MessageHandler
from app.utils.secure_logging import SecureLogger

logger = logging.getLogger(__name__)

# ================================
# NEW PIPELINE ENTRY POINT
# ================================

@shared_task(
    bind=True,
    name='audio_processing.process_audio_message'
)
def process_audio_message_task(self, message_data: Dict[str, Any], use_pipeline: bool = True):
    """
    Main audio processing task - routes to optimized or legacy pipeline
    
    Args:
        message_data: Message data from webhook
        use_pipeline: If True, uses new optimized pipeline. If False, uses legacy monolithic approach
    
    Returns:
        Task result
    """
    try:
        SecureLogger.safe_log_info(logger, "Audio processing requested", {
            'task_id': self.request.id,
            'message_id': message_data.get('message_id'),
            'use_pipeline': use_pipeline,
            'from_user': SecureLogger.mask_phone_number(message_data.get('from', ''))
        })
        
        if use_pipeline:
            # Use new optimized pipeline
            from app.tasks.pipeline_orchestrator import start_audio_processing
            pipeline_id = start_audio_processing(message_data, priority='normal')
            
            SecureLogger.safe_log_info(logger, "Optimized pipeline started", {
                'task_id': self.request.id,
                'pipeline_id': pipeline_id,
                'message_id': message_data.get('message_id')
            })
            
            return {
                'status': 'pipeline_started',
                'pipeline_id': pipeline_id,
                'message': 'Audio processing started with optimized pipeline',
                'task_id': self.request.id
            }
        else:
            # Use legacy monolithic approach
            return process_audio_message_legacy_task.delay(message_data).get()
            
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Audio processing routing failed", e, {
            'task_id': self.request.id,
            'message_id': message_data.get('message_id'),
            'use_pipeline': use_pipeline
        })
        raise

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    retry_backoff=True,
    retry_jitter=True,
    name='audio_processing.process_audio_message_legacy'
)
def process_audio_message_legacy_task(self, message_data: Dict[str, Any]):
    """
    Celery task for processing audio messages
    
    This is a wrapper around the existing MessageHandler.process_audio_message
    to maintain compatibility while adding Celery benefits.
    """
    try:
        SecureLogger.safe_log_info(logger, "Processing audio message via Celery", {
            'task_id': self.request.id,
            'message_type': message_data.get('type'),
            'from_user': SecureLogger.mask_phone_number(message_data.get('from', '')),
            'retry_count': self.request.retries
        })
        
        # Use existing MessageHandler
        handler = MessageHandler()
        
        # This will be an async function, we need to handle it properly
        import asyncio
        
        # Create new event loop for this task
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Run the async function
            result = loop.run_until_complete(
                handler.process_audio_message(message_data)
            )
            
            SecureLogger.safe_log_info(logger, "Audio processing completed successfully", {
                'task_id': self.request.id,
                'from_user': SecureLogger.mask_phone_number(message_data.get('from', ''))
            })
            
            return {
                'status': 'success',
                'message': 'Audio processed successfully',
                'task_id': self.request.id
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Audio processing failed", e, {
            'task_id': self.request.id,
            'from_user': SecureLogger.mask_phone_number(message_data.get('from', '')),
            'retry_count': self.request.retries
        })
        
        # Re-raise to trigger Celery retry mechanism
        raise

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 30},
    name='audio_processing.test_task'
)
def test_audio_task(self, x: int, y: int):
    """Simple test task for validation"""
    SecureLogger.safe_log_info(logger, "Test task executed", {
        'task_id': self.request.id,
        'x': x,
        'y': y
    })
    
    result = x + y
    
    return {
        'status': 'success',
        'result': result,
        'task_id': self.request.id
    }