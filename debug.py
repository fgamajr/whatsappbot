#!/usr/bin/env python3
"""
Teste isolado do Telegram - sem dependências do projeto
"""
import asyncio
import aiohttp
import os

# Token direto (para teste isolado)
TOKEN = "7957097790:AAGZ63n8o2_XMpeRncTMXiZ9e0VI6ux_fRg"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

async def test_telegram_simple():
    """Teste simples do Telegram"""
    print("🤖 TESTE SIMPLES TELEGRAM")
    print("=" * 30)
    
    # 1. Testar getMe
    print("1. 📋 Testando getMe...")
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/getMe") as response:
            result = await response.json()
            print(f"   Status: {response.status}")
            print(f"   Resultado: {result}")
    
    # 2. Testar sendMessage
    print("\n2. 💬 Testando sendMessage...")
    data = {
        "chat_id": "123456789",
        "text": "🤖 Teste simples!"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BASE_URL}/sendMessage", json=data) as response:
                result = await response.text()
                print(f"   Status: {response.status}")
                print(f"   Resposta: {result}")
                
                if response.status == 200:
                    print("   ✅ Envio bem-sucedido!")
                else:
                    print("   ❌ Envio falhou")
                    
    except Exception as e:
        print(f"   ❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_telegram_simple())