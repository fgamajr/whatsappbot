from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Dict, List
import logging
from datetime import datetime, timedelta
from app.services.recovery_service import RecoveryService
from app.infrastructure.database.repositories.interview import InterviewRepository
from app.domain.entities.interview import InterviewStatus

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/recovery/run")
async def run_recovery(background_tasks: BackgroundTasks):
    """Executa ciclo de recovery em background"""
    try:
        recovery_service = RecoveryService()
        background_tasks.add_task(recovery_service.run_recovery_cycle)
        
        return {
            "message": "Recovery cycle started in background",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to start recovery cycle", extra={
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recovery/status")
async def get_recovery_status():
    """Retorna status das entrevistas para monitoramento"""
    try:
        interview_repo = InterviewRepository()
        collection = await interview_repo._get_collection()
        
        # Contar por status
        pipeline = [
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        
        status_counts = {}
        async for doc in collection.aggregate(pipeline):
            status_counts[doc["_id"]] = doc["count"]
        
        # Buscar entrevistas órfãs
        cutoff_time = datetime.now() - timedelta(minutes=60)
        orphaned_count = await collection.count_documents({
            "status": {
                "$in": [
                    InterviewStatus.PROCESSING,
                    InterviewStatus.TRANSCRIBING,
                    InterviewStatus.ANALYZING
                ]
            },
            "started_at": {"$lt": cutoff_time}
        })
        
        # Buscar entrevistas para retry
        retry_cutoff = datetime.now() - timedelta(minutes=5)
        retry_ready_count = await collection.count_documents({
            "status": InterviewStatus.FAILED,
            "retry_count": {"$lt": 3},
            "last_retry_at": {"$lt": retry_cutoff}
        })
        
        return {
            "timestamp": datetime.now().isoformat(),
            "status_counts": status_counts,
            "orphaned_interviews": orphaned_count,
            "retry_ready": retry_ready_count,
            "total_interviews": sum(status_counts.values()) if status_counts else 0
        }
        
    except Exception as e:
        logger.error("Failed to get recovery status", extra={
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recovery/orphaned")
async def list_orphaned_interviews():
    """Lista entrevistas órfãs para debugging"""
    try:
        recovery_service = RecoveryService()
        orphaned = await recovery_service._find_orphaned_interviews()
        
        return {
            "count": len(orphaned),
            "interviews": [
                {
                    "id": interview.id,
                    "phone_number": interview.phone_number,
                    "status": interview.status,
                    "started_at": interview.started_at.isoformat() if interview.started_at else None,
                    "chunks_processed": interview.chunks_processed,
                    "chunks_total": interview.chunks_total,
                    "processing_time_minutes": (
                        datetime.now() - interview.started_at
                    ).total_seconds() / 60 if interview.started_at else 0
                }
                for interview in orphaned
            ]
        }
        
    except Exception as e:
        logger.error("Failed to list orphaned interviews", extra={
            "error": str(e)
        })
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recovery/interview/{interview_id}")
async def force_retry_interview(interview_id: str, background_tasks: BackgroundTasks):
    """Força retry de uma entrevista específica"""
    try:
        interview_repo = InterviewRepository()
        interview = await interview_repo.get_by_id(interview_id)
        
        if not interview:
            raise HTTPException(status_code=404, detail="Interview not found")
        
        recovery_service = RecoveryService()
        background_tasks.add_task(recovery_service._retry_interview, interview)
        
        return {
            "message": f"Retry scheduled for interview {interview_id}",
            "interview_id": interview_id,
            "current_status": interview.status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to force retry interview", extra={
            "error": str(e),
            "interview_id": interview_id
        })
        raise HTTPException(status_code=500, detail=str(e))
