from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging
from app.infrastructure.database.mongodb import MongoDB
from app.domain.entities.prompt import PromptTemplate, UserPromptPreference, PromptCategory, PromptStatus

logger = logging.getLogger(__name__)


class PromptRepository:
    """Repository for managing prompt templates in MongoDB"""
    
    def __init__(self):
        self.db: AsyncIOMotorDatabase = None
        self.collection_name = "prompts"
        self.preferences_collection = "user_prompt_preferences"
    
    async def _get_db(self) -> AsyncIOMotorDatabase:
        """Get database instance"""
        if self.db is None:
            self.db = await MongoDB.get_database()
        return self.db
    
    async def create(self, prompt: PromptTemplate) -> PromptTemplate:
        """Create a new prompt template"""
        try:
            db = await self._get_db()
            
            prompt_dict = prompt.model_dump()
            await db[self.collection_name].insert_one(prompt_dict)
            
            logger.info("Prompt created", extra={
                "prompt_id": prompt.id,
                "name": prompt.name,
                "category": prompt.category
            })
            
            return prompt
            
        except Exception as e:
            logger.error("Failed to create prompt", extra={
                "error": str(e),
                "prompt_name": prompt.name
            })
            raise
    
    async def get_by_id(self, prompt_id: str) -> Optional[PromptTemplate]:
        """Get prompt by ID"""
        try:
            db = await self._get_db()
            
            prompt_data = await db[self.collection_name].find_one({"id": prompt_id})
            if prompt_data:
                return PromptTemplate(**prompt_data)
            
            return None
            
        except Exception as e:
            logger.error("Failed to get prompt by ID", extra={
                "error": str(e),
                "prompt_id": prompt_id
            })
            raise
    
    async def get_by_short_code(self, short_code: str) -> Optional[PromptTemplate]:
        """Get prompt by short code"""
        try:
            db = await self._get_db()
            
            prompt_data = await db[self.collection_name].find_one({
                "short_code": short_code,
                "status": PromptStatus.ACTIVE
            })
            
            if prompt_data:
                return PromptTemplate(**prompt_data)
            
            return None
            
        except Exception as e:
            logger.error("Failed to get prompt by short code", extra={
                "error": str(e),
                "short_code": short_code
            })
            raise
    
    async def get_by_category(self, category: PromptCategory, active_only: bool = True) -> List[PromptTemplate]:
        """Get prompts by category"""
        try:
            db = await self._get_db()
            
            query = {"category": category}
            if active_only:
                query["status"] = PromptStatus.ACTIVE
            
            cursor = db[self.collection_name].find(query).sort("display_order", 1)
            prompts = []
            
            async for prompt_data in cursor:
                prompts.append(PromptTemplate(**prompt_data))
            
            return prompts
            
        except Exception as e:
            logger.error("Failed to get prompts by category", extra={
                "error": str(e),
                "category": category
            })
            raise
    
    async def get_all_active(self) -> List[PromptTemplate]:
        """Get all active prompts"""
        try:
            db = await self._get_db()
            
            cursor = db[self.collection_name].find({
                "status": PromptStatus.ACTIVE
            }).sort([("category", 1), ("display_order", 1)])
            
            prompts = []
            async for prompt_data in cursor:
                prompts.append(PromptTemplate(**prompt_data))
            
            return prompts
            
        except Exception as e:
            logger.error("Failed to get all active prompts", extra={
                "error": str(e)
            })
            raise
    
    async def update(self, prompt: PromptTemplate) -> PromptTemplate:
        """Update existing prompt"""
        try:
            db = await self._get_db()
            
            # Only update specific fields to avoid conflicts
            update_data = {
                "usage_count": prompt.usage_count,
                "last_used_at": prompt.last_used_at,
                "updated_at": prompt.updated_at
            }
            
            result = await db[self.collection_name].update_one(
                {"id": prompt.id},
                {"$set": update_data}
            )
            
            if result.matched_count == 0:
                raise ValueError(f"Prompt with ID {prompt.id} not found")
            
            logger.info("Prompt updated", extra={
                "prompt_id": prompt.id,
                "usage_count": prompt.usage_count
            })
            
            return prompt
            
        except Exception as e:
            logger.error("Failed to update prompt", extra={
                "error": str(e),
                "prompt_id": getattr(prompt, 'id', 'unknown')
            })
            raise
    
    async def delete(self, prompt_id: str) -> bool:
        """Delete prompt (soft delete by setting status to inactive)"""
        try:
            db = await self._get_db()
            
            result = await db[self.collection_name].update_one(
                {"id": prompt_id},
                {"$set": {"status": PromptStatus.INACTIVE}}
            )
            
            if result.matched_count > 0:
                logger.info("Prompt soft deleted", extra={
                    "prompt_id": prompt_id
                })
                return True
            
            return False
            
        except Exception as e:
            logger.error("Failed to delete prompt", extra={
                "error": str(e),
                "prompt_id": prompt_id
            })
            raise
    
    async def search(self, query: str, category: Optional[PromptCategory] = None) -> List[PromptTemplate]:
        """Search prompts by name, description, or tags"""
        try:
            db = await self._get_db()
            
            search_filter = {
                "$and": [
                    {"status": PromptStatus.ACTIVE},
                    {
                        "$or": [
                            {"name": {"$regex": query, "$options": "i"}},
                            {"description": {"$regex": query, "$options": "i"}},
                            {"tags": {"$in": [query]}}
                        ]
                    }
                ]
            }
            
            if category:
                search_filter["$and"].append({"category": category})
            
            cursor = db[self.collection_name].find(search_filter).sort("usage_count", -1)
            
            prompts = []
            async for prompt_data in cursor:
                prompts.append(PromptTemplate(**prompt_data))
            
            return prompts
            
        except Exception as e:
            logger.error("Failed to search prompts", extra={
                "error": str(e),
                "query": query
            })
            raise
    
    # User Preferences
    async def get_user_preference(self, user_id: str) -> Optional[UserPromptPreference]:
        """Get user's prompt preferences"""
        try:
            db = await self._get_db()
            
            pref_data = await db[self.preferences_collection].find_one({"user_id": user_id})
            if pref_data:
                return UserPromptPreference(**pref_data)
            
            return None
            
        except Exception as e:
            logger.error("Failed to get user preference", extra={
                "error": str(e),
                "user_id": user_id
            })
            raise
    
    async def save_user_preference(self, preference: UserPromptPreference) -> UserPromptPreference:
        """Save or update user's prompt preferences"""
        try:
            db = await self._get_db()
            
            pref_dict = preference.model_dump()
            await db[self.preferences_collection].replace_one(
                {"user_id": preference.user_id},
                pref_dict,
                upsert=True
            )
            
            logger.info("User preference saved", extra={
                "user_id": preference.user_id,
                "default_prompt_id": preference.default_prompt_id
            })
            
            return preference
            
        except Exception as e:
            logger.error("Failed to save user preference", extra={
                "error": str(e),
                "user_id": preference.user_id
            })
            raise
    
    async def get_popular_prompts(self, limit: int = 5) -> List[PromptTemplate]:
        """Get most used prompts"""
        try:
            db = await self._get_db()
            
            cursor = db[self.collection_name].find({
                "status": PromptStatus.ACTIVE
            }).sort("usage_count", -1).limit(limit)
            
            prompts = []
            async for prompt_data in cursor:
                prompts.append(PromptTemplate(**prompt_data))
            
            return prompts
            
        except Exception as e:
            logger.error("Failed to get popular prompts", extra={
                "error": str(e)
            })
            raise