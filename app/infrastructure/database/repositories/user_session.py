from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging
from datetime import datetime
from app.infrastructure.database.mongodb import MongoDB
from app.domain.entities.user_session import UserSession, SessionState

logger = logging.getLogger(__name__)


class UserSessionRepository:
    """Repository for managing user sessions in MongoDB"""
    
    def __init__(self):
        self.db: AsyncIOMotorDatabase = None
        self.collection_name = "user_sessions"
    
    async def _get_db(self) -> AsyncIOMotorDatabase:
        """Get database instance"""
        if self.db is None:
            self.db = await MongoDB.get_database()
        return self.db
    
    async def get_session(self, user_id: str) -> Optional[UserSession]:
        """Get user session, return None if expired or not found"""
        try:
            db = await self._get_db()
            
            session_data = await db[self.collection_name].find_one({"user_id": user_id})
            if not session_data:
                return None
            
            session = UserSession(**session_data)
            
            # Check if expired
            if session.is_expired():
                await self.delete_session(user_id)
                return None
            
            return session
            
        except Exception as e:
            logger.error("Failed to get user session", extra={
                "error": str(e),
                "user_id": user_id
            })
            return None
    
    async def save_session(self, session: UserSession) -> UserSession:
        """Save or update user session"""
        try:
            db = await self._get_db()
            
            session_dict = session.model_dump()
            await db[self.collection_name].replace_one(
                {"user_id": session.user_id},
                session_dict,
                upsert=True
            )
            
            logger.info("User session saved", extra={
                "user_id": session.user_id,
                "state": session.state
            })
            
            return session
            
        except Exception as e:
            logger.error("Failed to save user session", extra={
                "error": str(e),
                "user_id": session.user_id
            })
            raise
    
    async def delete_session(self, user_id: str) -> bool:
        """Delete user session"""
        try:
            db = await self._get_db()
            
            result = await db[self.collection_name].delete_one({"user_id": user_id})
            
            if result.deleted_count > 0:
                logger.info("User session deleted", extra={
                    "user_id": user_id
                })
                return True
            
            return False
            
        except Exception as e:
            logger.error("Failed to delete user session", extra={
                "error": str(e),
                "user_id": user_id
            })
            return False
    
    async def cleanup_expired_sessions(self):
        """Remove all expired sessions"""
        try:
            db = await self._get_db()
            
            current_time = datetime.now()
            result = await db[self.collection_name].delete_many({
                "expires_at": {"$lt": current_time}
            })
            
            if result.deleted_count > 0:
                logger.info("Cleaned up expired sessions", extra={
                    "deleted_count": result.deleted_count
                })
            
            return result.deleted_count
            
        except Exception as e:
            logger.error("Failed to cleanup expired sessions", extra={
                "error": str(e)
            })
            return 0