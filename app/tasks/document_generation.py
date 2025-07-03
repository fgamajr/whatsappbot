from celery import shared_task
from typing import Dict, Any, Optional
import logging
from app.utils.secure_logging import SecureLogger

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 30},
    retry_backoff=True,
    name='document_generation.generate_documents'
)
def generate_documents_task(self, transcript_data: Dict[str, Any], analysis_data: Dict[str, Any], 
                           interview_id: str):
    """
    Celery task for generating interview documents
    
    Args:
        transcript_data: Transcription result data
        analysis_data: Analysis result data  
        interview_id: Interview unique identifier
    """
    try:
        SecureLogger.safe_log_info(logger, "Generating documents via Celery", {
            'task_id': self.request.id,
            'interview_id': interview_id,
            'retry_count': self.request.retries
        })
        
        # Import here to avoid circular imports
        from app.services.document_generator import DocumentGenerator
        
        # Create new event loop for async operations
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            generator = DocumentGenerator()
            
            # Generate transcription document
            transcript_path = loop.run_until_complete(
                generator.generate_transcription_document(
                    transcript_data, 
                    interview_id
                )
            )
            
            # Generate analysis document  
            analysis_path = loop.run_until_complete(
                generator.generate_analysis_document(
                    analysis_data,
                    interview_id
                )
            )
            
            SecureLogger.safe_log_info(logger, "Documents generated successfully", {
                'task_id': self.request.id,
                'interview_id': interview_id,
                'transcript_doc': transcript_path is not None,
                'analysis_doc': analysis_path is not None
            })
            
            return {
                'status': 'success',
                'documents': {
                    'transcript': transcript_path,
                    'analysis': analysis_path
                },
                'interview_id': interview_id,
                'task_id': self.request.id
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Document generation failed", e, {
            'task_id': self.request.id,
            'interview_id': interview_id,
            'retry_count': self.request.retries
        })
        
        # Re-raise to trigger Celery retry
        raise

@shared_task(
    bind=True,
    name='document_generation.cleanup_temp_files'
)
def cleanup_temp_files_task(self, file_paths: list):
    """
    Clean up temporary files
    
    Args:
        file_paths: List of file paths to clean up
    """
    try:
        import os
        
        cleaned_count = 0
        for file_path in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    cleaned_count += 1
            except OSError as e:
                SecureLogger.safe_log_warning(logger, f"Failed to clean file {file_path}", {
                    'task_id': self.request.id,
                    'file_path': file_path,
                    'error': str(e)
                })
        
        SecureLogger.safe_log_info(logger, "File cleanup completed", {
            'task_id': self.request.id,
            'total_files': len(file_paths),
            'cleaned_files': cleaned_count
        })
        
        return {
            'status': 'success',
            'cleaned_files': cleaned_count,
            'total_files': len(file_paths)
        }
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "File cleanup failed", e, {
            'task_id': self.request.id,
            'file_count': len(file_paths)
        })
        
        # Don't retry cleanup tasks
        return {
            'status': 'failed',
            'error': str(e)
        }