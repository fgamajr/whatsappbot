#!/usr/bin/env python3
"""
Script para migrar entrevistas antigas para o novo formato
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.database.mongodb import MongoDB
from app.infrastructure.database.repositories.interview import InterviewRepository
from app.core.logging import setup_logging
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

async def migrate_interviews():
    """Migra entrevistas antigas"""
    try:
        interview_repo = InterviewRepository()
        collection = await interview_repo._get_collection()
        
        print("🔄 Migrando entrevistas antigas...")
        
        # Atualizar entrevistas que não têm campos de retry
        result1 = await collection.update_many(
            {"retry_count": {"$exists": False}},
            {"$set": {"retry_count": 0}}
        )
        
        result2 = await collection.update_many(
            {"last_retry_at": {"$exists": False}},
            {"$set": {"last_retry_at": None}}
        )
        
        # Remover campo simple_mode se existir
        result3 = await collection.update_many(
            {"simple_mode": {"$exists": True}},
            {"$unset": {"simple_mode": ""}}
        )
        
        print(f"✅ Migração concluída:")
        print(f"   - retry_count adicionado: {result1.modified_count}")
        print(f"   - last_retry_at adicionado: {result2.modified_count}")
        print(f"   - simple_mode removido: {result3.modified_count}")
        
    except Exception as e:
        print(f"❌ Erro na migração: {e}")

async def main():
    setup_logging(debug=settings.DEBUG)
    await MongoDB.connect()
    await migrate_interviews()
    await MongoDB.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
