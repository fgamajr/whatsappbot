from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class MongoDB:
    client: AsyncIOMotorClient = None
    database: AsyncIOMotorDatabase = None
    
    @classmethod
    async def connect(cls):
        """Create database connection"""
        try:
            cls.client = AsyncIOMotorClient(
                settings.MONGODB_URL,
                maxPoolSize=50,
                minPoolSize=10,
                serverSelectionTimeoutMS=5000,
            )
            
            # Test connection
            await cls.client.admin.command('ping')
            
            cls.database = cls.client[settings.DB_NAME]
            
            logger.info("MongoDB connected successfully", extra={
                "database": settings.DB_NAME,
                "url": settings.MONGODB_URL.split('@')[-1]  # Hide credentials
            })
            
        except Exception as e:
            logger.error("Failed to connect to MongoDB", extra={
                "error": str(e)
            })
            raise
    
    @classmethod
    async def disconnect(cls):
        """Close database connection"""
        if cls.client:
            cls.client.close()
            logger.info("MongoDB disconnected")
    
    @classmethod
    async def get_database(cls) -> AsyncIOMotorDatabase:
        """Get database instance"""
        if cls.database is None:
            await cls.connect()
        return cls.database
