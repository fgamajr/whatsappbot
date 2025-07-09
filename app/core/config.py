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
    GEMINI_MODEL: str = "gemini-1.5-pro"
    
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
    
    # Authorization & Support
    ADMIN_CONTACT_INFO: str = "📧 Envie um email para: suporte@empresa.com\n📱 WhatsApp: +55 11 99999-9999"
    
    # YouTube Download Settings
    YOUTUBE_MAX_DURATION: int = 7200  # 2 hours in seconds
    YOUTUBE_MAX_FILE_SIZE: int = 200 * 1024 * 1024  # 200MB in bytes
    YOUTUBE_DOWNLOAD_TIMEOUT: int = 300  # 5 minutes timeout
    YOUTUBE_QUALITY: str = "160+140/133+140/134+140/worst"  # Specific format combos that work
    
    # yt-dlp service settings
    YTDLP_SERVICE_URL: str = "http://localhost:8080"
    YTDLP_AUTO_UPDATE: bool = True
    YTDLP_UPDATE_INTERVAL_HOURS: int = 6


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()