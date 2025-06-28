#!/bin/bash

# =============================================================================
# DEPLOY RECOVERY SYSTEM - Interview Bot
# =============================================================================

set -e

echo "🚀 Implementando Sistema de Recovery..."
echo "======================================"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ROOT=$(pwd)

# Função para criar backup
create_backup() {
    echo -e "${YELLOW}📦 Criando backup dos arquivos existentes...${NC}"
    BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # Backup dos arquivos que vamos modificar
    FILES_TO_BACKUP=(
        "app/domain/entities/interview.py"
        "app/services/transcription.py"
        "app/services/message_handler.py"
        "app/api/v1/webhooks.py"
        "app/main.py"
        "app/prompts/interview_analysis.py"
        "app/core/config.py"
    )
    
    for file in "${FILES_TO_BACKUP[@]}"; do
        if [ -f "$file" ]; then
            mkdir -p "$BACKUP_DIR/$(dirname "$file")"
            cp "$file" "$BACKUP_DIR/$file"
            echo "  ✅ Backup: $file"
        fi
    done
    
    echo -e "${GREEN}✅ Backup criado em: $BACKUP_DIR${NC}"
}

# Função para criar diretórios
create_directories() {
    echo -e "${YELLOW}📁 Criando diretórios necessários...${NC}"
    mkdir -p app/services
    mkdir -p app/api/v1
    mkdir -p scripts
    mkdir -p logs
    echo -e "${GREEN}✅ Diretórios criados${NC}"
}

# Função para criar RecoveryService
create_recovery_service() {
    echo -e "${YELLOW}📝 Criando RecoveryService...${NC}"
    
    cat > app/services/recovery_service.py << 'RECOVERY_SERVICE_EOF'
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
RECOVERY_SERVICE_EOF

    echo "  ✅ RecoveryService criado"
}

# Função para criar Recovery API
create_recovery_api() {
    echo -e "${YELLOW}📝 Criando Recovery API...${NC}"
    
    cat > app/api/v1/recovery.py << 'RECOVERY_API_EOF'
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
RECOVERY_API_EOF

    echo "  ✅ Recovery API criado"
}

# Função para criar script de recovery
create_recovery_script() {
    echo -e "${YELLOW}📝 Criando script de recovery...${NC}"
    
    cat > scripts/recovery.py << 'RECOVERY_SCRIPT_EOF'
#!/usr/bin/env python3
"""
Recovery Script - Recupera entrevistas órfãs e com falhas

Usage:
  python scripts/recovery.py              # Executa recovery completo
  python scripts/recovery.py --status     # Apenas mostra status
  python scripts/recovery.py --cleanup 30 # Remove entrevistas antigas (30+ dias)
"""

import asyncio
import sys
import os
import argparse

# Adicionar o diretório do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.recovery_service import RecoveryService
from app.infrastructure.database.mongodb import MongoDB
from app.infrastructure.database.repositories.interview import InterviewRepository
from app.core.logging import setup_logging
from app.core.config import settings
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


async def show_status():
    """Mostra status das entrevistas"""
    try:
        interview_repo = InterviewRepository()
        collection = await interview_repo._get_collection()
        
        print("\n📊 STATUS DAS ENTREVISTAS")
        print("=" * 50)
        
        # Contar por status
        pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
        
        status_counts = {}
        async for doc in collection.aggregate(pipeline):
            status_counts[doc["_id"]] = doc["count"]
        
        for status, count in status_counts.items():
            print(f"{status.upper()}: {count}")
        
        # Entrevistas órfãs
        cutoff_time = datetime.now() - timedelta(minutes=60)
        orphaned_count = await collection.count_documents({
            "status": {"$in": ["processing", "transcribing", "analyzing"]},
            "started_at": {"$lt": cutoff_time}
        })
        
        print(f"\n🚨 ÓRFÃS (>1h processando): {orphaned_count}")
        
        # Entrevistas para retry
        retry_cutoff = datetime.now() - timedelta(minutes=5)
        retry_count = await collection.count_documents({
            "status": "failed",
            "retry_count": {"$lt": 3},
            "last_retry_at": {"$lt": retry_cutoff}
        })
        
        print(f"🔄 PRONTAS PARA RETRY: {retry_count}")
        print(f"📈 TOTAL: {sum(status_counts.values())}")
        
    except Exception as e:
        logger.error("Failed to show status", extra={"error": str(e)})
        print(f"❌ Erro ao buscar status: {e}")


async def run_recovery():
    """Executa recovery completo"""
    try:
        print("\n🔄 INICIANDO RECOVERY...")
        
        recovery_service = RecoveryService()
        await recovery_service.run_recovery_cycle()
        
        print("✅ Recovery concluído com sucesso!")
        
    except Exception as e:
        logger.error("Recovery failed", extra={"error": str(e)})
        print(f"❌ Recovery falhou: {e}")


async def cleanup_old(days: int):
    """Remove entrevistas antigas"""
    try:
        if days < 7:
            print("❌ Mínimo de 7 dias para cleanup")
            return
        
        print(f"\n🗑️ LIMPANDO ENTREVISTAS COM {days}+ DIAS...")
        
        recovery_service = RecoveryService()
        await recovery_service.cleanup_old_interviews(days)
        
        print("✅ Cleanup concluído!")
        
    except Exception as e:
        logger.error("Cleanup failed", extra={"error": str(e)})
        print(f"❌ Cleanup falhou: {e}")


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Recovery System for Interview Bot")
    parser.add_argument("--status", action="store_true", help="Show status only")
    parser.add_argument("--cleanup", type=int, metavar="DAYS", help="Cleanup interviews older than N days")
    
    args = parser.parse_args()
    
    try:
        # Setup
        setup_logging(debug=settings.DEBUG)
        await MongoDB.connect()
        
        print(f"🚀 Recovery System - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if args.status:
            await show_status()
        elif args.cleanup:
            await cleanup_old(args.cleanup)
        else:
            await show_status()
            await run_recovery()
            await show_status()
        
    except KeyboardInterrupt:
        print("\n⏹️ Interrompido pelo usuário")
    except Exception as e:
        logger.error("Script failed", extra={"error": str(e)})
        print(f"❌ Erro: {e}")
        sys.exit(1)
    finally:
        await MongoDB.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
RECOVERY_SCRIPT_EOF

    echo "  ✅ Script de recovery criado"
}

# Função para atualizar Interview entity
update_interview_entity() {
    echo -e "${YELLOW}✏️ Atualizando Interview entity...${NC}"
    
    # Verificar se já tem os campos
    if grep -q "retry_count" app/domain/entities/interview.py; then
        echo "  ⚠️ Interview entity já tem campos de retry"
        return
    fi
    
    # Fazer backup primeiro
    cp app/domain/entities/interview.py app/domain/entities/interview.py.bak
    
    # Adicionar campos de retry antes do último método
    sed -i '/def mark_processing/i\
    # Recovery fields\
    retry_count: int = 0\
    last_retry_at: Optional[datetime] = None\
' app/domain/entities/interview.py
    
    echo "  ✅ Interview entity atualizada"
}

# Função para atualizar main.py
update_main_py() {
    echo -e "${YELLOW}✏️ Atualizando main.py...${NC}"
    
    # Verificar se já tem recovery routes
    if grep -q "recovery_router" app/main.py; then
        echo "  ⚠️ Main.py já tem recovery routes"
        return
    fi
    
    # Fazer backup primeiro
    cp app/main.py app/main.py.bak
    
    # Adicionar import e rota de recovery antes do @app.get("/")
    sed -i '/@app.get("\/")/ i\
# Recovery routes\
try:\
    from app.api.v1.recovery import router as recovery_router\
    app.include_router(recovery_router, prefix="", tags=["recovery"])\
    logger.info("Recovery endpoints enabled")\
except ImportError as e:\
    logger.warning("Recovery endpoints not available", extra={"error": str(e)})\
\
' app/main.py
    
    echo "  ✅ Main.py atualizado"
}

# Função para configurar permissões
set_permissions() {
    echo -e "${YELLOW}🔐 Configurando permissões...${NC}"
    chmod +x scripts/recovery.py
    echo -e "${GREEN}✅ Permissões configuradas${NC}"
}

# Função para testar a instalação
test_installation() {
    echo -e "${YELLOW}🧪 Testando instalação...${NC}"
    
    # Verificar se os arquivos foram criados
    FILES_TO_CHECK=(
        "app/services/recovery_service.py"
        "app/api/v1/recovery.py"
        "scripts/recovery.py"
    )
    
    for file in "${FILES_TO_CHECK[@]}"; do
        if [ -f "$file" ]; then
            echo -e "  ✅ $file"
        else
            echo -e "  ❌ $file ${RED}(FALTANDO)${NC}"
        fi
    done
    
    # Testar sintaxe Python
    echo -e "\n🐍 Verificando sintaxe Python..."
    if python3 -m py_compile app/services/recovery_service.py 2>/dev/null; then
        echo -e "  ✅ recovery_service.py"
    else
        echo -e "  ❌ recovery_service.py ${RED}(ERRO DE SINTAXE)${NC}"
    fi
    
    if python3 -m py_compile scripts/recovery.py 2>/dev/null; then
        echo -e "  ✅ scripts/recovery.py"
    else
        echo -e "  ❌ scripts/recovery.py ${RED}(ERRO DE SINTAXE)${NC}"
    fi
}

# Função para mostrar próximos passos
show_next_steps() {
    echo -e "\n${GREEN}🎉 INSTALAÇÃO CONCLUÍDA!${NC}"
    echo -e "${BLUE}=====================================${NC}"
    echo ""
    echo -e "${YELLOW}📋 PRÓXIMOS PASSOS:${NC}"
    echo ""
    echo "1. 🧪 TESTAR O RECOVERY:"
    echo "   python scripts/recovery.py --status"
    echo ""
    echo "2. 🔄 EXECUTAR RECOVERY DAS ENTREVISTAS ÓRFÃS:"
    echo "   python scripts/recovery.py"
    echo ""
    echo "3. 🌐 TESTAR VIA API:"
    echo "   curl http://localhost:8000/recovery/status"
    echo ""
    echo "4. ⏰ CONFIGURAR CRON JOB (OPCIONAL):"
    echo "   crontab -e"
    echo "   # Adicionar linha:"
    echo "   */10 * * * * cd $(pwd) && python scripts/recovery.py >> logs/recovery.log 2>&1"
    echo ""
    echo "5. 🚀 REINICIAR O BOT:"
    echo "   # Ctrl+C para parar"
    echo "   python -m app.main"
    echo ""
    echo -e "${GREEN}✨ Sistema de Recovery está pronto!${NC}"
}

# EXECUÇÃO PRINCIPAL
main() {
    echo "Executando deploy do sistema de recovery..."
    
    create_backup
    create_directories
    create_recovery_service
    create_recovery_api
    create_recovery_script
    update_interview_entity
    update_main_py
    set_permissions
    test_installation
    show_next_steps
}

# Executar se não estiver sendo sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi