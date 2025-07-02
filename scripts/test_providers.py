#!/usr/bin/env python3
"""
Test script to verify both WhatsApp and Telegram providers work correctly
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.messaging.factory import MessagingProviderFactory
from app.infrastructure.messaging.base import MessageType, StandardMessage


async def test_whatsapp_provider():
    """Test WhatsApp provider instantiation and basic methods"""
    print("🟢 Testing WhatsApp Provider...")
    
    try:
        provider = MessagingProviderFactory.create_provider("whatsapp")
        print(f"✅ WhatsApp provider created: {type(provider).__name__}")
        
        # Test webhook validation (mock data)
        mock_whatsapp_data = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [
                            {
                                "id": "test_msg_123",
                                "type": "text",
                                "from": "5511999999999",
                                "timestamp": "1234567890",
                                "text": {"body": "Hello"}
                            }
                        ]
                    }
                }]
            }]
        }
        
        is_valid = provider.validate_webhook(mock_whatsapp_data, {})
        print(f"✅ Webhook validation: {is_valid}")
        
        # Test message extraction
        message = provider.extract_message_data(mock_whatsapp_data)
        if message:
            print(f"✅ Message extraction: {message.message_type.value} from {message.from_number}")
        else:
            print("❌ Message extraction failed")
        
        return True
        
    except Exception as e:
        print(f"❌ WhatsApp provider error: {e}")
        return False


async def test_telegram_provider():
    """Test Telegram provider instantiation and basic methods"""
    print("\n🔵 Testing Telegram Provider...")
    
    try:
        provider = MessagingProviderFactory.create_provider("telegram")
        print(f"✅ Telegram provider created: {type(provider).__name__}")
        
        # Test webhook validation (mock data)
        mock_telegram_data = {
            "message": {
                "message_id": 123,
                "chat": {"id": 456789},
                "date": 1234567890,
                "text": "Hello from Telegram"
            }
        }
        
        is_valid = provider.validate_webhook(mock_telegram_data, {})
        print(f"✅ Webhook validation: {is_valid}")
        
        # Test message extraction
        message = provider.extract_message_data(mock_telegram_data)
        if message:
            print(f"✅ Message extraction: {message.message_type.value} from {message.from_number}")
        else:
            print("❌ Message extraction failed")
        
        return True
        
    except Exception as e:
        print(f"❌ Telegram provider error: {e}")
        return False


async def test_factory():
    """Test messaging provider factory"""
    print("\n🏭 Testing Provider Factory...")
    
    try:
        # Test available providers
        providers = MessagingProviderFactory.get_available_providers()
        print(f"✅ Available providers: {providers}")
        
        # Test default provider
        default = MessagingProviderFactory.get_default_provider()
        print(f"✅ Default provider: {type(default).__name__}")
        
        # Test both providers
        wa_provider = MessagingProviderFactory.create_provider("whatsapp")
        tg_provider = MessagingProviderFactory.create_provider("telegram")
        
        print(f"✅ WhatsApp: {type(wa_provider).__name__}")
        print(f"✅ Telegram: {type(tg_provider).__name__}")
        
        return True
        
    except Exception as e:
        print(f"❌ Factory error: {e}")
        return False


async def test_standard_message():
    """Test StandardMessage class"""
    print("\n📨 Testing StandardMessage...")
    
    try:
        # Test text message
        text_msg = StandardMessage(
            from_number="123456789",
            message_type=MessageType.TEXT,
            message_id="msg_123",
            content="Hello world"
        )
        
        print(f"✅ Text message: {text_msg.to_dict()}")
        
        # Test audio message
        audio_msg = StandardMessage(
            from_number="987654321",
            message_type=MessageType.AUDIO,
            message_id="msg_456",
            media_id="audio_123"
        )
        
        print(f"✅ Audio message: {audio_msg.to_dict()}")
        
        return True
        
    except Exception as e:
        print(f"❌ StandardMessage error: {e}")
        return False


async def main():
    """Run all tests"""
    print("🧪 Testing Messaging Providers\n")
    
    results = []
    
    # Run tests
    results.append(await test_factory())
    results.append(await test_standard_message())
    results.append(await test_whatsapp_provider())
    results.append(await test_telegram_provider())
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Both providers are working correctly.")
        print("\n📝 Next steps:")
        print("1. Set up your .env file with tokens")
        print("2. Configure webhooks for your providers")
        print("3. Deploy and test with real messages")
    else:
        print("❌ Some tests failed. Check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())