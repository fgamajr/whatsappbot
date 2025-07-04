from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Depends
from fastapi.responses import FileResponse
from typing import List, Optional
import os
from datetime import datetime
import logging

from app.services.export_manager import export_manager
from app.infrastructure.database.repositories.interview import InterviewRepository
from app.tasks.export_tasks import export_interview_task, export_batch_interviews_task
from app.utils.secure_logging import SecureLogger

router = APIRouter(prefix="/export", tags=["export"])
logger = logging.getLogger(__name__)

@router.get("/formats")
async def get_supported_formats():
    """Get list of supported export formats"""
    return {
        "status": "success",
        "data": {
            "supported_formats": export_manager.SUPPORTED_FORMATS,
            "descriptions": {
                "docx": "Microsoft Word document with rich formatting",
                "pdf": "Portable Document Format (requires docx2pdf)",
                "txt": "Plain text format",
                "json": "Structured JSON data",
                "csv": "Comma-separated values for data analysis",
                "xlsx": "Microsoft Excel spreadsheet with multiple sheets",
                "zip": "Compressed archive containing multiple files"
            }
        }
    }

@router.post("/interview/{interview_id}")
async def export_interview(
    interview_id: str,
    format_type: str = Query("docx", description="Export format"),
    include_analysis: bool = Query(True, description="Include analysis in export"),
    include_metadata: bool = Query(True, description="Include metadata in export"),
    async_export: bool = Query(False, description="Process export asynchronously")
):
    """Export a single interview in specified format"""
    
    if format_type not in export_manager.SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported format: {format_type}. Supported: {export_manager.SUPPORTED_FORMATS}"
        )
    
    try:
        # Get interview data
        repo = InterviewRepository()
        interview = await repo.get_by_id(interview_id)
        
        if not interview:
            raise HTTPException(status_code=404, detail="Interview not found")
        
        # Convert to dict for processing
        interview_data = {
            'id': str(interview.id),
            'created_at': interview.created_at.isoformat() if interview.created_at else None,
            'status': interview.status.value if interview.status else 'unknown',
            'transcript': interview.transcript or '',
            'analysis': interview.analysis or '',
            'duration': interview.duration_minutes or 0,
            'chunks_total': interview.chunks_total or 0,
            'chunks_processed': interview.chunks_processed or 0,
            'phone_number': interview.phone_number or '',
            'metrics': {
                'processing_time_minutes': interview.duration_minutes or 0,
                'transcript_length': len(interview.transcript or ''),
                'analysis_length': len(interview.analysis or ''),
                'chunks_completion_rate': (
                    (interview.chunks_processed or 0) / max(interview.chunks_total or 1, 1) * 100
                )
            }
        }
        
        if async_export:
            # Process asynchronously
            task = export_interview_task.delay(
                interview_data, format_type, include_analysis, include_metadata
            )
            
            return {
                "status": "accepted",
                "message": "Export started asynchronously",
                "task_id": task.id,
                "check_status_url": f"/export/status/{task.id}"
            }
        else:
            # Process synchronously
            file_path = export_manager.export_interview(
                interview_data, format_type, include_analysis, include_metadata
            )
            
            if not os.path.exists(file_path):
                raise HTTPException(status_code=500, detail="Export file not generated")
            
            # Get filename from path
            filename = os.path.basename(file_path)
            
            SecureLogger.safe_log_info(logger, "Interview export completed", {
                'interview_id': interview_id,
                'format': format_type,
                'file_path': file_path
            })
            
            return FileResponse(
                path=file_path,
                filename=filename,
                media_type='application/octet-stream'
            )
            
    except HTTPException:
        raise
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Export failed", e, {
            'interview_id': interview_id,
            'format': format_type
        })
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@router.post("/batch")
async def export_batch_interviews(
    interview_ids: List[str],
    format_type: str = Query("zip", description="Batch export format"),
    individual_format: str = Query("docx", description="Format for individual files in batch"),
    async_export: bool = Query(True, description="Process export asynchronously")
):
    """Export multiple interviews as a batch"""
    
    if not interview_ids:
        raise HTTPException(status_code=400, detail="No interview IDs provided")
    
    if len(interview_ids) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 interviews per batch export")
    
    if format_type not in ['zip', 'xlsx', 'csv']:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported batch format: {format_type}. Supported: zip, xlsx, csv"
        )
    
    try:
        # Get interview data
        repo = InterviewRepository()
        interviews = []
        not_found = []
        
        for interview_id in interview_ids:
            interview = await repo.get_by_id(interview_id)
            if interview:
                interview_data = {
                    'id': str(interview.id),
                    'created_at': interview.created_at.isoformat() if interview.created_at else None,
                    'status': interview.status.value if interview.status else 'unknown',
                    'transcript': interview.transcript or '',
                    'analysis': interview.analysis or '',
                    'duration': interview.duration_minutes or 0,
                    'chunks_total': interview.chunks_total or 0,
                    'chunks_processed': interview.chunks_processed or 0,
                    'phone_number': interview.phone_number or '',
                    'metrics': {
                        'processing_time_minutes': interview.duration_minutes or 0,
                        'transcript_length': len(interview.transcript or ''),
                        'analysis_length': len(interview.analysis or ''),
                        'chunks_completion_rate': (
                            (interview.chunks_processed or 0) / max(interview.chunks_total or 1, 1) * 100
                        )
                    }
                }
                interviews.append(interview_data)
            else:
                not_found.append(interview_id)
        
        if not interviews:
            raise HTTPException(status_code=404, detail="No valid interviews found")
        
        if async_export:
            # Process asynchronously
            task = export_batch_interviews_task.delay(
                interviews, format_type, individual_format
            )
            
            response = {
                "status": "accepted",
                "message": "Batch export started asynchronously",
                "task_id": task.id,
                "check_status_url": f"/export/status/{task.id}",
                "interviews_found": len(interviews),
                "interviews_requested": len(interview_ids)
            }
            
            if not_found:
                response["interviews_not_found"] = not_found
            
            return response
        else:
            # Process synchronously
            file_path = export_manager.export_batch(interviews, format_type, individual_format)
            
            if not os.path.exists(file_path):
                raise HTTPException(status_code=500, detail="Batch export file not generated")
            
            filename = os.path.basename(file_path)
            
            SecureLogger.safe_log_info(logger, "Batch export completed", {
                'interviews_count': len(interviews),
                'format': format_type,
                'file_path': file_path
            })
            
            return FileResponse(
                path=file_path,
                filename=filename,
                media_type='application/octet-stream'
            )
            
    except HTTPException:
        raise
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Batch export failed", e, {
            'interview_count': len(interview_ids),
            'format': format_type
        })
        raise HTTPException(status_code=500, detail=f"Batch export failed: {str(e)}")

@router.get("/status/{task_id}")
async def get_export_status(task_id: str):
    """Get status of async export task"""
    try:
        from celery.result import AsyncResult
        
        task_result = AsyncResult(task_id)
        
        if task_result.ready():
            if task_result.successful():
                result = task_result.result
                
                # Check if file exists
                if isinstance(result, str) and os.path.exists(result):
                    return {
                        "status": "completed",
                        "file_ready": True,
                        "download_url": f"/export/download/{task_id}",
                        "filename": os.path.basename(result)
                    }
                else:
                    return {
                        "status": "completed",
                        "file_ready": False,
                        "error": "Export file not found"
                    }
            else:
                return {
                    "status": "failed",
                    "error": str(task_result.result)
                }
        else:
            return {
                "status": "processing",
                "state": task_result.state
            }
            
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to get export status", e, {
            'task_id': task_id
        })
        raise HTTPException(status_code=500, detail="Failed to get export status")

@router.get("/download/{task_id}")
async def download_export_file(task_id: str):
    """Download completed export file"""
    try:
        from celery.result import AsyncResult
        
        task_result = AsyncResult(task_id)
        
        if not task_result.ready():
            raise HTTPException(status_code=202, detail="Export still in progress")
        
        if not task_result.successful():
            raise HTTPException(status_code=500, detail="Export task failed")
        
        file_path = task_result.result
        
        if not isinstance(file_path, str) or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Export file not found")
        
        filename = os.path.basename(file_path)
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='application/octet-stream'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Failed to download export file", e, {
            'task_id': task_id
        })
        raise HTTPException(status_code=500, detail="Failed to download export file")

@router.get("/history")
async def get_export_history(
    limit: int = Query(20, description="Number of recent exports"),
    interview_id: Optional[str] = Query(None, description="Filter by interview ID")
):
    """Get export history (simplified implementation)"""
    
    # This is a simplified implementation
    # In production, you'd want to store export history in the database
    
    return {
        "status": "success",
        "message": "Export history feature requires database schema extension",
        "data": {
            "exports": [],
            "total": 0,
            "note": "To implement full export history, add an 'exports' table to track all export operations"
        }
    }

@router.delete("/cleanup")
async def cleanup_temp_files(
    older_than_hours: int = Query(24, description="Delete files older than X hours")
):
    """Clean up temporary export files"""
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
            'deleted_count': deleted_count,
            'older_than_hours': older_than_hours
        })
        
        return {
            "status": "success",
            "message": f"Cleanup completed",
            "files_deleted": deleted_count
        }
        
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Export cleanup failed", e)
        raise HTTPException(status_code=500, detail="Cleanup failed")