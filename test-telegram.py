#!/usr/bin/env python3
"""
Script para debugar o TelegramProvider isoladamente
"""
import asyncio
import sys
import os

# Adicionar path do projeto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.messaging.telegram.client import TelegramProvider
from app.core.config import settings

async def test_telegram_provider():
    """Testa o TelegramProvider isoladamente"""
    print("🔍 DEBUGANDO TELEGRAM PROVIDER")
    print("=" * 50)
    
    # 1. Verificar configuração
    print(f"1. 🔧 Token configurado: {bool(settings.TELEGRAM_BOT_TOKEN)}")
    if settings.TELEGRAM_BOT_TOKEN:
        print(f"   Token (primeiros 10 chars): {settings.TELEGRAM_BOT_TOKEN[:10]}...")
    else:
        print("   ❌ TOKEN VAZIO!")
        return
    
    # 2. Criar provider
    try:
        provider = TelegramProvider()
        print("2. ✅ TelegramProvider criado")
        print(f"   Base URL: {provider.base_url}")
    except Exception as e:
        print(f"2. ❌ Erro ao criar provider: {e}")
        return
    
    # 3. Testar envio de mensagem
    print("\n3. 🧪 Testando envio de mensagem...")
    try:
        # Usar um chat_id de teste
        test_chat_id = "123456789"
        test_message = "🤖 Teste do bot!"
        
        result = await provider.send_text_message(test_chat_id, test_message)
        print(f"   Resultado: {result}")
        
        if result:
            print("   ✅ Envio bem-sucedido!")
        else:
            print("   ❌ Envio falhou (sem exceção)")
            
    except Exception as e:
        print(f"   ❌ ERRO no envio: {e}")
        print(f"   Tipo do erro: {type(e).__name__}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_telegram_provider())