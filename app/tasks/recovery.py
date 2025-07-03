from celery import shared_task
from typing import List, Dict, Any
import logging
from app.utils.secure_logging import SecureLogger

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    name='recovery.check_orphaned_interviews'
)
def check_orphaned_interviews_task(self):
    """
    Periodic task to check for orphaned interviews and recover them
    
    This replaces the manual scheduling in recovery_service.py
    """
    try:
        SecureLogger.safe_log_info(logger, "Starting orphaned interviews check", {
            'task_id': self.request.id
        })
        
        # Import here to avoid circular imports
        from app.services.recovery_service import RecoveryService
        
        # Create new event loop for async operations
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            recovery_service = RecoveryService()
            
            # Get orphaned interviews
            orphaned_interviews = loop.run_until_complete(
                recovery_service.get_orphaned_interviews()
            )
            
            recovered_count = 0
            failed_count = 0
            
            # Process each orphaned interview
            for interview in orphaned_interviews:
                try:
                    # Schedule recovery task
                    recover_interview_task.delay(interview['_id'])
                    recovered_count += 1
                    
                except Exception as e:
                    SecureLogger.safe_log_error(logger, "Failed to schedule recovery", e, {
                        'interview_id': interview['_id'],
                        'task_id': self.request.id
                    })
                    failed_count += 1
            
            SecureLogger.safe_log_info(logger, "Orphaned interviews check completed", {
                'task_id': self.request.id,
                'total_orphaned': len(orphaned_interviews),
                'recovery_scheduled': recovered_count,
                'failed_to_schedule': failed_count
            })
            
            return {
                'status': 'success',
                'total_orphaned': len(orphaned_interviews),
                'recovery_scheduled': recovered_count,
                'failed_to_schedule': failed_count,
                'task_id': self.request.id
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Orphaned interviews check failed", e, {
            'task_id': self.request.id
        })
        
        return {
            'status': 'failed',
            'error': str(e),
            'task_id': self.request.id
        }

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 300},  # 5 minute delay
    retry_backoff=True,
    name='recovery.recover_interview'
)
def recover_interview_task(self, interview_id: str):
    """
    Recover a specific interview
    
    Args:
        interview_id: ID of the interview to recover
    """
    try:
        SecureLogger.safe_log_info(logger, "Starting interview recovery", {
            'task_id': self.request.id,
            'interview_id': interview_id,
            'retry_count': self.request.retries
        })
        
        # Import here to avoid circular imports
        from app.services.recovery_service import RecoveryService
        
        # Create new event loop for async operations
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            recovery_service = RecoveryService()
            
            # Attempt recovery
            result = loop.run_until_complete(
                recovery_service.recover_interview(interview_id)
            )
            
            if result:
                SecureLogger.safe_log_info(logger, "Interview recovery successful", {
                    'task_id': self.request.id,
                    'interview_id': interview_id
                })
                
                return {
                    'status': 'success',
                    'interview_id': interview_id,
                    'task_id': self.request.id
                }
            else:
                # Recovery failed but not due to exception
                SecureLogger.safe_log_warning(logger, "Interview recovery returned False", {
                    'task_id': self.request.id,
                    'interview_id': interview_id
                })
                
                return {
                    'status': 'failed',
                    'interview_id': interview_id,
                    'reason': 'Recovery service returned False',
                    'task_id': self.request.id
                }
                
        finally:
            loop.close()
            
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Interview recovery failed", e, {
            'task_id': self.request.id,
            'interview_id': interview_id,
            'retry_count': self.request.retries
        })
        
        # Re-raise to trigger Celery retry
        raise