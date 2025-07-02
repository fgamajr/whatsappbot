from typing import Dict, Type
from app.infrastructure.messaging.base import MessagingProvider
from app.infrastructure.messaging.whatsapp.client import WhatsAppProvider
from app.infrastructure.messaging.telegram.client import TelegramProvider
from app.core.config import settings


class MessagingProviderFactory:
    """Factory for creating messaging provider instances"""
    
    _providers: Dict[str, Type[MessagingProvider]] = {
        "whatsapp": WhatsAppProvider,
        "telegram": TelegramProvider
    }
    
    @classmethod
    def create_provider(cls, provider_name: str) -> MessagingProvider:
        """Create a messaging provider instance"""
        provider_class = cls._providers.get(provider_name.lower())
        if not provider_class:
            raise ValueError(f"Unknown messaging provider: {provider_name}")
        
        return provider_class()
    
    @classmethod
    def get_default_provider(cls) -> MessagingProvider:
        """Get the default messaging provider based on configuration"""
        default_provider = getattr(settings, 'DEFAULT_MESSAGING_PROVIDER', 'whatsapp')
        return cls.create_provider(default_provider)
    
    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Get list of available provider names"""
        return list(cls._providers.keys())
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[MessagingProvider]):
        """Register a new messaging provider"""
        cls._providers[name.lower()] = provider_class