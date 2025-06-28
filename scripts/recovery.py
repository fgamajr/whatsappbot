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
