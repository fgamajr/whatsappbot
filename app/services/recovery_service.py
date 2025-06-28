from datetime import datetime, timedelta
from typing import List, Optional
import logging
import asyncio
from app.domain.entities.interview import Interview, InterviewStatus
from app.infrastructure.database.repositories.interview import InterviewRepository
from app.services.message_handler import MessageHandler
from app.infrastructure.whatsapp.client import WhatsAppClient
from app.core.config import settings

logger = logging.getLogger(__name__)


class RecoveryService:
    """
    Serviço para recuperar entrevistas órfãs e com falhas
    """
    
    def __init__(self):
        self.interview_repo = InterviewRepository()
        self.whatsapp = WhatsAppClient()
        self.message_handler = MessageHandler()
        
        # Configurações de recovery
        self.max_processing_time_minutes = 60  # Considera órfã após 1 hora
        self.max_retry_attempts = 3
        self.retry_delay_minutes = 5
    
    async def run_recovery_cycle(self):
        """
        Executa um ciclo completo de recuperação
        """
        logger.info("Starting recovery cycle")
        
        try:
            # Buscar entrevistas órfãs
            orphaned_interviews = await self._find_orphaned_interviews()
            
            if orphaned_interviews:
                logger.info("Found orphaned interviews", extra={
                    "count": len(orphaned_interviews)
                })
                
                for interview in orphaned_interviews:
                    await self._recover_interview(interview)
            
            # Buscar entrevistas para retry
            retry_interviews = await self._find_retry_candidates()
            
            if retry_interviews:
                logger.info("Found interviews ready for retry", extra={
                    "count": len(retry_interviews)
                })
                
                for interview in retry_interviews:
                    await self._retry_interview(interview)
            
            logger.info("Recovery cycle completed")
            
        except Exception as e:
            logger.error("Recovery cycle failed", extra={
                "error": str(e)
            })
    
    async def _find_orphaned_interviews(self) -> List[Interview]:
        """
        Encontra entrevistas órfãs (processando há muito tempo)
        """
        try:
            collection = await self.interview_repo._get_collection()
            
            # Buscar entrevistas em processamento há mais de X minutos
            cutoff_time = datetime.now() - timedelta(minutes=self.max_processing_time_minutes)
            
            cursor = collection.find({
                "status": {
                    "$in": [
                        InterviewStatus.PROCESSING,
                        InterviewStatus.TRANSCRIBING,
                        InterviewStatus.ANALYZING
                    ]
                },
                "started_at": {"$lt": cutoff_time}
            })
            
            orphaned = []
            async for doc in cursor:
                interview = Interview(**doc)
                
                # Verificar se realmente está órfã (não foi atualizada recentemente)
                if interview.started_at and interview.started_at < cutoff_time:
                    orphaned.append(interview)
            
            return orphaned
            
        except Exception as e:
            logger.error("Failed to find orphaned interviews", extra={
                "error": str(e)
            })
            return []
    
    async def _find_retry_candidates(self) -> List[Interview]:
        """
        Encontra entrevistas marcadas para retry que já passaram do delay
        """
        try:
            collection = await self.interview_repo._get_collection()
            
            # Buscar entrevistas marcadas para retry
            cutoff_time = datetime.now() - timedelta(minutes=self.retry_delay_minutes)
            
            cursor = collection.find({
                "status": InterviewStatus.FAILED,
                "retry_count": {"$lt": self.max_retry_attempts},
                "last_retry_at": {"$lt": cutoff_time}
            })
            
            candidates = []
            async for doc in cursor:
                interview = Interview(**doc)
                candidates.append(interview)
            
            return candidates
            
        except Exception as e:
            logger.error("Failed to find retry candidates", extra={
                "error": str(e)
            })
            return []
    
    async def _recover_interview(self, interview: Interview):
        """
        Recupera uma entrevista órfã
        """
        try:
            logger.info("Recovering orphaned interview", extra={
                "interview_id": interview.id,
                "phone_number": interview.phone_number,
                "stuck_status": interview.status,
                "processing_time_minutes": (
                    datetime.now() - interview.started_at
                ).total_seconds() / 60 if interview.started_at else 0
            })
            
            # Adicionar campos de retry se não existirem
            if not hasattr(interview, 'retry_count'):
                interview.retry_count = 0
            if not hasattr(interview, 'last_retry_at'):
                interview.last_retry_at = None
            
            # Marcar para retry
            interview.retry_count += 1
            interview.last_retry_at = datetime.now()
            interview.status = InterviewStatus.FAILED
            interview.error = f"Recovered from orphaned state. Retry {interview.retry_count}/{self.max_retry_attempts}"
            
            await self.interview_repo.update(interview)
            
            # Notificar usuário
            await self.whatsapp.send_text_message(
                interview.phone_number,
                f"🔄 Recuperando processamento interrompido...\n"
                f"ID: {interview.id[:8]} - Tentativa {interview.retry_count}/{self.max_retry_attempts}"
            )
            
        except Exception as e:
            logger.error("Failed to recover interview", extra={
                "error": str(e),
                "interview_id": interview.id
            })
    
    async def _retry_interview(self, interview: Interview):
        """
        Tenta reprocessar uma entrevista
        """
        try:
            if interview.retry_count >= self.max_retry_attempts:
                await self._mark_permanently_failed(interview)
                return
            
            logger.info("Retrying interview", extra={
                "interview_id": interview.id,
                "retry_attempt": interview.retry_count + 1,
                "max_attempts": self.max_retry_attempts
            })
            
            # Reset para reprocessamento
            interview.status = InterviewStatus.PENDING
            interview.error = None
            interview.retry_count += 1
            interview.last_retry_at = datetime.now()
            
            await self.interview_repo.update(interview)
            
            # Recriar message_data para reprocessamento
            message_data = {
                "from": interview.phone_number,
                "type": "audio",
                "message_id": interview.message_id,
                "media_id": interview.audio_id
            }
            
            # Reprocessar em background
            asyncio.create_task(
                self.message_handler.process_audio_message(message_data)
            )
            
        except Exception as e:
            logger.error("Failed to retry interview", extra={
                "error": str(e),
                "interview_id": interview.id
            })
    
    async def _mark_permanently_failed(self, interview: Interview):
        """
        Marca entrevista como permanentemente falhada
        """
        try:
            interview.status = InterviewStatus.FAILED
            interview.error = f"Permanently failed after {self.max_retry_attempts} attempts"
            interview.completed_at = datetime.now()
            
            await self.interview_repo.update(interview)
            
            logger.error("Interview permanently failed", extra={
                "interview_id": interview.id,
                "phone_number": interview.phone_number,
                "retry_attempts": interview.retry_count
            })
            
            # Notificar usuário
            await self.whatsapp.send_text_message(
                interview.phone_number,
                f"❌ Processamento falhou definitivamente\n"
                f"ID: {interview.id[:8]}\n"
                f"Tentativas: {interview.retry_count}/{self.max_retry_attempts}\n\n"
                f"Entre em contato com o suporte se necessário."
            )
            
        except Exception as e:
            logger.error("Failed to mark interview as permanently failed", extra={
                "error": str(e),
                "interview_id": interview.id
            })
    
    async def cleanup_old_interviews(self, days_old: int = 30):
        """
        Remove entrevistas muito antigas do banco
        """
        try:
            collection = await self.interview_repo._get_collection()
            
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            result = await collection.delete_many({
                "created_at": {"$lt": cutoff_date},
                "status": {"$in": [InterviewStatus.COMPLETED, InterviewStatus.FAILED]}
            })
            
            logger.info("Cleaned up old interviews", extra={
                "deleted_count": result.deleted_count,
                "days_old": days_old
            })
            
        except Exception as e:
            logger.error("Failed to cleanup old interviews", extra={
                "error": str(e)
            })
