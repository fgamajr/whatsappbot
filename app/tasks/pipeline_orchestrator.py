from celery import chain, group, chord
from typing import Dict, Any
import logging
from app.tasks.audio_pipeline import (
    download_audio_task,
    convert_and_chunk_audio_task,
    transcribe_chunk_task,
    combine_transcripts_task,
    generate_analysis_task,
    generate_and_send_documents_task
)
from app.utils.secure_logging import SecureLogger

logger = logging.getLogger(__name__)

def create_audio_processing_pipeline(message_data: Dict[str, Any]) -> chain:
    """
    Create the complete audio processing pipeline using Celery primitives
    
    Pipeline Flow:
    1. Download Audio (sequential)
    2. Convert & Chunk (sequential) 
    3. Transcribe Chunks (PARALLEL) -> Combine (sequential)
    4. Generate Analysis (sequential)
    5. Generate Documents (sequential)
    
    Args:
        message_data: Message data from webhook
        
    Returns:
        Celery chain object ready for execution
    """
    
    SecureLogger.safe_log_info(logger, "Creating audio processing pipeline", {
        'message_id': message_data.get('message_id'),
        'from_user': SecureLogger.mask_phone_number(message_data.get('from', ''))
    })
    
    # Step 1: Download and validate audio
    step1 = download_audio_task.s(message_data)
    
    # Step 2: Convert to MP3 and create chunks
    step2 = convert_and_chunk_audio_task.s()
    
    # Step 3: Create dynamic parallel transcription based on chunk count
    # This will be built dynamically in the callback
    step3 = create_parallel_transcription_workflow.s()
    
    # Step 4: Generate analysis
    step4 = generate_analysis_task.s()
    
    # Step 5: Generate and send documents
    step5 = generate_and_send_documents_task.s()
    
    # Create the main pipeline chain
    pipeline = chain(
        step1,
        step2, 
        step3,
        step4,
        step5
    )
    
    SecureLogger.safe_log_info(logger, "Audio processing pipeline created", {
        'message_id': message_data.get('message_id'),
        'pipeline_steps': 5
    })
    
    return pipeline

def create_parallel_transcription_workflow(interview_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a parallel transcription workflow based on the number of chunks
    
    This function creates a chord: group of parallel transcription tasks + combine callback
    
    Args:
        interview_data: Data from convert_and_chunk_audio_task
        
    Returns:
        Updated interview_data with transcript
    """
    
    SecureLogger.safe_log_info(logger, "Creating parallel transcription workflow", {
        'interview_id': interview_data['interview_id'],
        'chunks_count': len(interview_data['chunks_hex'])
    })
    
    # Create parallel transcription tasks for each chunk
    transcription_tasks = []
    
    for chunk_index, chunk_hex in enumerate(interview_data['chunks_hex']):
        chunk_data = {
            'chunk_hex': chunk_hex,
            'chunk_index': chunk_index,
            'interview_id': interview_data['interview_id'],
            'phone_number': interview_data['phone_number'],
            'total_chunks': interview_data['chunks_total']
        }
        
        transcription_tasks.append(transcribe_chunk_task.s(chunk_data))
    
    # Create a chord: parallel transcription + combine callback
    parallel_transcription = chord(
        group(transcription_tasks),  # Parallel execution of all chunks
        combine_transcripts_task.s(interview_data)  # Callback with all results
    )
    
    SecureLogger.safe_log_info(logger, "Parallel transcription workflow created", {
        'interview_id': interview_data['interview_id'],
        'parallel_tasks': len(transcription_tasks)
    })
    
    # Execute the chord and return its result
    result = parallel_transcription.apply()
    return result.get()  # Wait for completion and return the combined result

def create_optimized_pipeline_for_small_audio(message_data: Dict[str, Any]) -> chain:
    """
    Create an optimized pipeline for small audio files (< 10MB)
    
    For small files, we can skip chunking and use a simpler pipeline
    
    Args:
        message_data: Message data from webhook
        
    Returns:
        Optimized Celery chain
    """
    from app.tasks.audio_pipeline import (
        download_audio_task,
        transcribe_single_file_task,  # We'll create this
        generate_analysis_task,
        generate_and_send_documents_task
    )
    
    SecureLogger.safe_log_info(logger, "Creating optimized pipeline for small audio", {
        'message_id': message_data.get('message_id')
    })
    
    pipeline = chain(
        download_audio_task.s(message_data),
        transcribe_single_file_task.s(),  # Skip chunking for small files
        generate_analysis_task.s(),
        generate_and_send_documents_task.s()
    )
    
    return pipeline

def create_priority_pipeline(message_data: Dict[str, Any], priority: str = 'normal') -> chain:
    """
    Create a pipeline with specified priority routing
    
    Args:
        message_data: Message data from webhook
        priority: 'high', 'normal', or 'low'
        
    Returns:
        Celery chain with priority routing
    """
    
    # Map priority to queue names
    queue_mapping = {
        'high': 'high_priority',
        'normal': 'audio_processing', 
        'low': 'maintenance'
    }
    
    queue_name = queue_mapping.get(priority, 'audio_processing')
    
    SecureLogger.safe_log_info(logger, "Creating priority pipeline", {
        'message_id': message_data.get('message_id'),
        'priority': priority,
        'queue': queue_name
    })
    
    # Create pipeline with queue routing
    pipeline = create_audio_processing_pipeline(message_data)
    
    # Apply queue routing to all tasks in the pipeline
    # Note: This is a simplified approach - in practice, you might want 
    # different queues for different types of tasks
    for task in pipeline.tasks:
        task.set(queue=queue_name)
    
    return pipeline

def get_pipeline_status(pipeline_result) -> Dict[str, Any]:
    """
    Get comprehensive status of a running pipeline
    
    Args:
        pipeline_result: Result object from pipeline execution
        
    Returns:
        Status information
    """
    try:
        status_info = {
            'pipeline_id': pipeline_result.id if hasattr(pipeline_result, 'id') else 'unknown',
            'state': pipeline_result.state if hasattr(pipeline_result, 'state') else 'unknown',
            'current_task': 'unknown',
            'progress_percent': 0,
            'steps_completed': 0,
            'total_steps': 5,
            'estimated_time_remaining': 'calculating...'
        }
        
        # This is a simplified status - in practice, you'd track each step
        if hasattr(pipeline_result, 'state'):
            if pipeline_result.state == 'PENDING':
                status_info.update({
                    'current_task': 'Downloading audio',
                    'progress_percent': 10
                })
            elif pipeline_result.state == 'PROGRESS':
                # You could embed more detailed progress info in the result
                status_info.update({
                    'current_task': 'Processing',
                    'progress_percent': 50
                })
            elif pipeline_result.state == 'SUCCESS':
                status_info.update({
                    'current_task': 'Completed',
                    'progress_percent': 100,
                    'steps_completed': 5
                })
        
        return status_info
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to get pipeline status", e)
        return {
            'pipeline_id': 'unknown',
            'state': 'error',
            'error': str(e)
        }

# ================================
# SIMPLIFIED PIPELINE FUNCTIONS
# ================================

def start_audio_processing(message_data: Dict[str, Any], priority: str = 'normal') -> str:
    """
    Start audio processing pipeline - main entry point
    
    Args:
        message_data: Message data from webhook
        priority: Priority level for processing
        
    Returns:
        Pipeline task ID for tracking
    """
    
    SecureLogger.safe_log_info(logger, "Starting audio processing pipeline", {
        'message_id': message_data.get('message_id'),
        'priority': priority,
        'from_user': SecureLogger.mask_phone_number(message_data.get('from', ''))
    })
    
    # Create and start the pipeline
    pipeline = create_audio_processing_pipeline(message_data)
    result = pipeline.apply_async()
    
    SecureLogger.safe_log_info(logger, "Audio processing pipeline started", {
        'pipeline_id': result.id,
        'message_id': message_data.get('message_id')
    })
    
    return result.id

def start_express_processing(message_data: Dict[str, Any]) -> str:
    """
    Start express processing for small/urgent audio files
    
    Args:
        message_data: Message data from webhook
        
    Returns:
        Pipeline task ID for tracking
    """
    
    SecureLogger.safe_log_info(logger, "Starting express audio processing", {
        'message_id': message_data.get('message_id')
    })
    
    # Use high priority pipeline
    pipeline = create_priority_pipeline(message_data, priority='high')
    result = pipeline.apply_async()
    
    return result.id

# ================================
# ERROR HANDLING & RECOVERY
# ================================

def retry_failed_pipeline(pipeline_id: str, step_to_retry: str = 'all') -> str:
    """
    Retry a failed pipeline from a specific step
    
    Args:
        pipeline_id: Original pipeline ID
        step_to_retry: Which step to retry from
        
    Returns:
        New pipeline task ID
    """
    
    SecureLogger.safe_log_info(logger, "Retrying failed pipeline", {
        'original_pipeline_id': pipeline_id,
        'retry_step': step_to_retry
    })
    
    # In a real implementation, you'd:
    # 1. Retrieve the original pipeline state
    # 2. Determine which step failed
    # 3. Restart from that step with preserved data
    # 4. This is a simplified version
    
    # For now, return a placeholder
    return f"retry_{pipeline_id}"

def cleanup_failed_pipeline(pipeline_id: str):
    """
    Clean up resources from a failed pipeline
    
    Args:
        pipeline_id: Pipeline ID to clean up
    """
    
    SecureLogger.safe_log_info(logger, "Cleaning up failed pipeline", {
        'pipeline_id': pipeline_id
    })
    
    # In practice, this would:
    # 1. Clean up any temporary files
    # 2. Update interview status
    # 3. Notify user of failure
    # 4. Schedule retry if appropriate