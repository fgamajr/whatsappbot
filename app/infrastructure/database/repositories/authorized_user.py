from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging
from datetime import datetime
from app.infrastructure.database.mongodb import MongoDB
from app.domain.entities.authorized_user import AuthorizedUser, Platform, UserStatus

logger = logging.getLogger(__name__)


class AuthorizedUserRepository:
    """Repository for managing authorized users in MongoDB"""
    
    def __init__(self):
        self.db: AsyncIOMotorDatabase = None
        self.collection_name = "authorized_users"
    
    async def _get_db(self) -> AsyncIOMotorDatabase:
        """Get database instance"""
        if self.db is None:
            self.db = await MongoDB.get_database()
        return self.db
    
    async def _ensure_indexes(self):
        """Ensure database indexes for performance"""
        try:
            db = await self._get_db()
            
            # Compound index for platform and identifier (primary lookup)
            await db[self.collection_name].create_index([
                ("platform", 1),
                ("platform_identifier", 1)
            ], unique=True)
            
            # Index for status queries
            await db[self.collection_name].create_index([("status", 1)])
            
            # Index for expiration cleanup
            await db[self.collection_name].create_index([("expires_at", 1)])
            
        except Exception as e:
            logger.warning("Failed to ensure indexes", extra={"error": str(e)})
    
    async def get_user(self, platform: Platform, platform_identifier: str) -> Optional[AuthorizedUser]:
        """Get authorized user by platform and identifier"""
        try:
            db = await self._get_db()
            
            user_data = await db[self.collection_name].find_one({
                "platform": platform,
                "platform_identifier": platform_identifier
            })
            
            if not user_data:
                return None
            
            return AuthorizedUser(**user_data)
            
        except Exception as e:
            logger.error("Failed to get authorized user", extra={
                "error": str(e),
                "platform": platform,
                "platform_identifier": platform_identifier
            })
            return None
    
    async def get_user_by_unified_id(self, unified_id: str) -> Optional[AuthorizedUser]:
        """Get user by unified ID (e.g., 'wa:5511999999999')"""
        try:
            if unified_id.startswith("wa:"):
                platform = Platform.WHATSAPP
                identifier = unified_id[3:]
            elif unified_id.startswith("tg:"):
                platform = Platform.TELEGRAM
                identifier = unified_id[3:]
            else:
                logger.warning("Invalid unified_id format", extra={"unified_id": unified_id})
                return None
            
            return await self.get_user(platform, identifier)
            
        except Exception as e:
            logger.error("Failed to get user by unified_id", extra={
                "error": str(e),
                "unified_id": unified_id
            })
            return None
    
    async def save_user(self, user: AuthorizedUser) -> AuthorizedUser:
        """Save or update authorized user"""
        try:
            db = await self._get_db()
            await self._ensure_indexes()
            
            user.updated_at = datetime.now()
            user_dict = user.model_dump()
            
            await db[self.collection_name].replace_one(
                {
                    "platform": user.platform,
                    "platform_identifier": user.platform_identifier
                },
                user_dict,
                upsert=True
            )
            
            logger.info("Authorized user saved", extra={
                "unified_id": user.unified_id,
                "display_name": user.display_name,
                "status": user.status
            })
            
            return user
            
        except Exception as e:
            logger.error("Failed to save authorized user", extra={
                "error": str(e),
                "unified_id": user.unified_id
            })
            raise
    
    async def delete_user(self, platform: Platform, platform_identifier: str) -> bool:
        """Delete authorized user"""
        try:
            db = await self._get_db()
            
            result = await db[self.collection_name].delete_one({
                "platform": platform,
                "platform_identifier": platform_identifier
            })
            
            if result.deleted_count > 0:
                logger.info("Authorized user deleted", extra={
                    "platform": platform,
                    "platform_identifier": platform_identifier
                })
                return True
            
            return False
            
        except Exception as e:
            logger.error("Failed to delete authorized user", extra={
                "error": str(e),
                "platform": platform,
                "platform_identifier": platform_identifier
            })
            return False
    
    async def list_users(
        self, 
        platform: Optional[Platform] = None,
        status: Optional[UserStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuthorizedUser]:
        """List authorized users with optional filters"""
        try:
            db = await self._get_db()
            
            query = {}
            if platform:
                query["platform"] = platform
            if status:
                query["status"] = status
            
            cursor = db[self.collection_name].find(query).skip(offset).limit(limit)
            user_data_list = await cursor.to_list(length=limit)
            
            return [AuthorizedUser(**user_data) for user_data in user_data_list]
            
        except Exception as e:
            logger.error("Failed to list authorized users", extra={
                "error": str(e),
                "platform": platform,
                "status": status
            })
            return []
    
    async def count_users(
        self, 
        platform: Optional[Platform] = None,
        status: Optional[UserStatus] = None
    ) -> int:
        """Count authorized users with optional filters"""
        try:
            db = await self._get_db()
            
            query = {}
            if platform:
                query["platform"] = platform
            if status:
                query["status"] = status
            
            return await db[self.collection_name].count_documents(query)
            
        except Exception as e:
            logger.error("Failed to count authorized users", extra={
                "error": str(e),
                "platform": platform,
                "status": status
            })
            return 0
    
    async def update_usage(self, platform: Platform, platform_identifier: str) -> bool:
        """Increment usage counters for a user"""
        try:
            user = await self.get_user(platform, platform_identifier)
            if not user:
                return False
            
            user.record_message_usage()
            await self.save_user(user)
            return True
            
        except Exception as e:
            logger.error("Failed to update user usage", extra={
                "error": str(e),
                "platform": platform,
                "platform_identifier": platform_identifier
            })
            return False
    
    async def cleanup_expired_users(self) -> int:
        """Remove or mark expired users"""
        try:
            db = await self._get_db()
            
            current_time = datetime.now()
            result = await db[self.collection_name].update_many(
                {
                    "expires_at": {"$lt": current_time},
                    "status": {"$ne": UserStatus.EXPIRED}
                },
                {"$set": {"status": UserStatus.EXPIRED, "updated_at": current_time}}
            )
            
            if result.modified_count > 0:
                logger.info("Marked expired users", extra={
                    "expired_count": result.modified_count
                })
            
            return result.modified_count
            
        except Exception as e:
            logger.error("Failed to cleanup expired users", extra={
                "error": str(e)
            })
            return 0
    
    async def get_usage_stats(self) -> dict:
        """Get platform usage statistics"""
        try:
            db = await self._get_db()
            
            pipeline = [
                {
                    "$group": {
                        "_id": "$platform",
                        "total_users": {"$sum": 1},
                        "active_users": {
                            "$sum": {"$cond": [{"$eq": ["$status", "active"]}, 1, 0]}
                        },
                        "total_messages": {"$sum": "$usage_stats.total_messages"},
                        "daily_messages": {"$sum": "$usage_stats.daily_count"},
                        "monthly_messages": {"$sum": "$usage_stats.monthly_count"}
                    }
                }
            ]
            
            cursor = db[self.collection_name].aggregate(pipeline)
            stats = {}
            
            async for result in cursor:
                stats[result["_id"]] = {
                    "total_users": result["total_users"],
                    "active_users": result["active_users"],
                    "total_messages": result["total_messages"],
                    "daily_messages": result["daily_messages"],
                    "monthly_messages": result["monthly_messages"]
                }
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get usage stats", extra={"error": str(e)})
            return {}