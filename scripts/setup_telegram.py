#!/usr/bin/env python3
"""
Script to set up Telegram webhook for the Interview Bot
"""
import asyncio
import aiohttp
import sys
from typing import Optional


async def set_telegram_webhook(bot_token: str, webhook_url: str) -> bool:
    """Set Telegram webhook URL"""
    url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    
    data = {
        "url": webhook_url,
        "allowed_updates": ["message"]
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data) as response:
            result = await response.json()
            
            if result.get("ok"):
                print(f"✅ Telegram webhook set successfully!")
                print(f"📍 Webhook URL: {webhook_url}")
                return True
            else:
                print(f"❌ Failed to set webhook: {result.get('description')}")
                return False


async def get_webhook_info(bot_token: str) -> Optional[dict]:
    """Get current webhook information"""
    url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            result = await response.json()
            
            if result.get("ok"):
                return result["result"]
            return None


async def get_bot_info(bot_token: str) -> Optional[dict]:
    """Get bot information"""
    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            result = await response.json()
            
            if result.get("ok"):
                return result["result"]
            return None


async def main():
    if len(sys.argv) < 3:
        print("Usage: python setup_telegram.py <BOT_TOKEN> <YOUR_DOMAIN>")
        print("Example: python setup_telegram.py 123456:ABC-DEF https://yourdomain.com")
        sys.exit(1)
    
    bot_token = sys.argv[1]
    domain = sys.argv[2].rstrip('/')
    webhook_url = f"{domain}/webhook/telegram"
    
    print("🤖 Setting up Telegram Bot...")
    print(f"📱 Bot Token: {bot_token[:10]}...")
    print(f"🌐 Domain: {domain}")
    print(f"🔗 Webhook URL: {webhook_url}")
    print()
    
    # Get bot info
    print("📋 Getting bot information...")
    bot_info = await get_bot_info(bot_token)
    if bot_info:
        print(f"✅ Bot: @{bot_info['username']} ({bot_info['first_name']})")
        print(f"🆔 Bot ID: {bot_info['id']}")
    else:
        print("❌ Invalid bot token")
        sys.exit(1)
    
    print()
    
    # Check current webhook
    print("🔍 Checking current webhook...")
    webhook_info = await get_webhook_info(bot_token)
    if webhook_info:
        current_url = webhook_info.get("url", "")
        if current_url:
            print(f"📍 Current webhook: {current_url}")
        else:
            print("📍 No webhook currently set")
        
        print(f"🔄 Pending updates: {webhook_info.get('pending_update_count', 0)}")
    
    print()
    
    # Set new webhook
    print("⚙️ Setting new webhook...")
    success = await set_telegram_webhook(bot_token, webhook_url)
    
    if success:
        print()
        print("🎉 Setup complete!")
        print()
        print("📝 Next steps:")
        print("1. Add TELEGRAM_BOT_TOKEN=<your_token> to your .env file")
        print("2. Make sure your server is running and accessible")
        print("3. Test by sending a message to your bot")
        print()
        print("🧪 Test commands:")
        print("- Send 'help' to see bot features")
        print("- Send voice message to test transcription")
    else:
        print("❌ Setup failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())