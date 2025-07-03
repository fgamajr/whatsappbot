from functools import lru_cache
from typing import Optional

# Imports corretos para Pydantic V2
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Estrutura correta, usando model_config e sem a 'class Config'
    model_config = ConfigDict(env_file=".env", case_sensitive=True)

    # App
    APP_NAME: str = "Interview Bot"
    VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # Messaging Providers
    DEFAULT_MESSAGING_PROVIDER: str = "whatsapp"
    
    # WhatsApp
    WHATSAPP_TOKEN: str
    WHATSAPP_VERIFY_TOKEN: str
    PHONE_NUMBER_ID: str
    WHATSAPP_API_VERSION: str = "v18.0"
    
    # Telegram
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_API_ID: Optional[int] = None
    TELEGRAM_API_HASH: Optional[str] = None
    
    # AI Services
    OPENAI_API_KEY: str
    GEMINI_API_KEY: str
    WHISPER_MODEL: str = "whisper-1"
    
    # Database
    MONGODB_URL: str
    DB_NAME: str = "interview_bot"
    
    # Processing
    AUDIO_CHUNK_MINUTES: int = 15
    MAX_RETRIES: int = 3
    MAX_CACHE_SIZE: int = 1000
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 10
    RATE_LIMIT_PER_HOUR: int = 100


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()