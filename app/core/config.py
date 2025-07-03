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
    WHATSAPP_WEBHOOK_SECRET: str  # For signature verification
    PHONE_NUMBER_ID: str
    WHATSAPP_API_VERSION: str = "v18.0"
    
    # Telegram
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_API_ID: Optional[int] = None
    TELEGRAM_API_HASH: Optional[str] = None
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = None  # For signature verification
    
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
    
    # Redis (optional - falls back to in-memory if not configured)
    REDIS_URL: Optional[str] = None
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Celery Configuration
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"      # Separate DB for broker
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"  # Separate DB for results
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: list = ["json"]
    CELERY_TIMEZONE: str = "UTC"
    CELERY_ENABLE_UTC: bool = True
    
    # Task Configuration
    CELERY_TASK_SOFT_TIME_LIMIT: int = 1800  # 30 minutes
    CELERY_TASK_TIME_LIMIT: int = 2100       # 35 minutes  
    CELERY_TASK_MAX_RETRIES: int = 3
    CELERY_TASK_DEFAULT_RETRY_DELAY: int = 60
    CELERY_TASK_ACKS_LATE: bool = True
    CELERY_TASK_REJECT_ON_WORKER_LOST: bool = True
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = 1
    
    # Celery Beat (Periodic Tasks)
    CELERY_BEAT_SCHEDULE: dict = {}
    
    # Pipeline Configuration
    USE_OPTIMIZED_PIPELINE: bool = True  # Feature flag for new pipeline
    PIPELINE_SMALL_AUDIO_THRESHOLD_MB: float = 10.0  # Threshold for small audio optimization
    PIPELINE_PARALLEL_CHUNK_LIMIT: int = 10  # Max parallel chunks to prevent overload


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()