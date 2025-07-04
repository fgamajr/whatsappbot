from celery import shared_task
from typing import Dict, List
import logging
from app.services.export_manager import export_manager
from app.utils.secure_logging import SecureLogger
from app.infrastructure.prometheus_metrics import prometheus_task_metrics

logger = logging.getLogger(__name__)

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
@prometheus_task_metrics
def export_interview_task(self, interview_data: Dict, format_type: str, include_analysis: bool = True, include_metadata: bool = True):
    """Export single interview asynchronously"""
    
    SecureLogger.safe_log_info(logger, "Starting async interview export", {
        'task_id': self.request.id,
        'interview_id': interview_data.get('id'),
        'format': format_type
    })
    
    try:
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 0,
                'total': 100,
                'status': 'Preparing export...'
            }
        )
        
        # Perform export
        file_path = export_manager.export_interview(
            interview_data, format_type, include_analysis, include_metadata
        )
        
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 100,
                'total': 100,
                'status': 'Export completed successfully'
            }
        )
        
        SecureLogger.safe_log_info(logger, "Async interview export completed", {
            'task_id': self.request.id,
            'interview_id': interview_data.get('id'),
            'file_path': file_path
        })
        
        return file_path
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Async interview export failed", e, {
            'task_id': self.request.id,
            'interview_id': interview_data.get('id'),
            'format': format_type
        })
        
        self.update_state(
            state='FAILURE',
            meta={
                'current': 0,
                'total': 100,
                'status': f'Export failed: {str(e)}'
            }
        )
        
        raise

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 120})
@prometheus_task_metrics
def export_batch_interviews_task(self, interviews: List[Dict], format_type: str = 'zip', individual_format: str = 'docx'):
    """Export multiple interviews asynchronously"""
    
    SecureLogger.safe_log_info(logger, "Starting async batch export", {
        'task_id': self.request.id,
        'interview_count': len(interviews),
        'format': format_type,
        'individual_format': individual_format
    })
    
    try:
        total_interviews = len(interviews)
        
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={
                'current': 0,
                'total': total_interviews,
                'status': 'Starting batch export...'
            }
        )
        
        # For ZIP exports, we need to track individual progress
        if format_type == 'zip':
            # Override the export manager to provide progress updates
            file_path = self._export_batch_with_progress(interviews, format_type, individual_format)
        else:
            # Single file exports (CSV, XLSX)
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': total_interviews // 2,
                    'total': total_interviews,
                    'status': 'Processing batch export...'
                }
            )
            
            file_path = export_manager.export_batch(interviews, format_type, individual_format)
        
        # Final update
        self.update_state(
            state='PROGRESS',
            meta={
                'current': total_interviews,
                'total': total_interviews,
                'status': 'Batch export completed successfully'
            }
        )
        
        SecureLogger.safe_log_info(logger, "Async batch export completed", {
            'task_id': self.request.id,
            'interview_count': len(interviews),
            'file_path': file_path
        })
        
        return file_path
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Async batch export failed", e, {
            'task_id': self.request.id,
            'interview_count': len(interviews),
            'format': format_type
        })
        
        self.update_state(
            state='FAILURE',
            meta={
                'current': 0,
                'total': len(interviews),
                'status': f'Batch export failed: {str(e)}'
            }
        )
        
        raise

def _export_batch_with_progress(self, interviews: List[Dict], format_type: str, individual_format: str) -> str:
    """Export batch with progress tracking for ZIP format"""
    import os
    import tempfile
    import zipfile
    from datetime import datetime
    
    total_interviews = len(interviews)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_filename = f"entrevistas_batch_{timestamp}.zip"
    zip_path = os.path.join(tempfile.gettempdir(), zip_filename)
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for i, interview in enumerate(interviews):
            try:
                # Update progress
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': i,
                        'total': total_interviews,
                        'status': f'Exporting interview {i+1}/{total_interviews}...'
                    }
                )
                
                # Export individual interview
                file_path = export_manager.export_interview(interview, individual_format, True, True)
                
                # Add to ZIP with organized name
                interview_id = interview.get('id', 'unknown')
                archive_name = f"entrevista_{interview_id}.{individual_format}"
                zipf.write(file_path, archive_name)
                
                # Clean up individual file
                os.remove(file_path)
                
            except Exception as e:
                SecureLogger.safe_log_error(logger, "Failed to add interview to batch", e, {
                    'interview_id': interview.get('id'),
                    'format': individual_format
                })
                # Continue with other interviews
                continue
    
    return zip_path

@shared_task(bind=True)
@prometheus_task_metrics
def cleanup_export_files_task(self, older_than_hours: int = 24):
    """Clean up old export files"""
    
    SecureLogger.safe_log_info(logger, "Starting export files cleanup", {
        'task_id': self.request.id,
        'older_than_hours': older_than_hours
    })
    
    try:
        import tempfile
        import time
        
        temp_dir = tempfile.gettempdir()
        deleted_count = 0
        current_time = time.time()
        cutoff_time = current_time - (older_than_hours * 3600)
        
        # Look for export files
        export_patterns = [
            'entrevista_', 'transcricao_', 'analise_', 'entrevistas_batch_'
        ]
        
        for filename in os.listdir(temp_dir):
            if any(pattern in filename for pattern in export_patterns):
                file_path = os.path.join(temp_dir, filename)
                if os.path.isfile(file_path):
                    file_time = os.path.getmtime(file_path)
                    if file_time < cutoff_time:
                        try:
                            os.remove(file_path)
                            deleted_count += 1
                        except OSError:
                            pass  # File might be in use
        
        SecureLogger.safe_log_info(logger, "Export files cleanup completed", {
            'task_id': self.request.id,
            'deleted_count': deleted_count,
            'older_than_hours': older_than_hours
        })
        
        return {
            'deleted_count': deleted_count,
            'older_than_hours': older_than_hours
        }
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Export cleanup failed", e, {
            'task_id': self.request.id
        })
        raise

# Periodic cleanup task (to be added to CELERY_BEAT_SCHEDULE)
@shared_task
@prometheus_task_metrics  
def periodic_export_cleanup():
    """Periodic cleanup of export files (runs daily)"""
    return cleanup_export_files_task.delay(older_than_hours=24)