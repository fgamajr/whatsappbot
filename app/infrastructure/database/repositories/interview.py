from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorCollection
from app.domain.entities.interview import Interview, InterviewStatus
from app.infrastructure.database.mongodb import MongoDB
from app.core.exceptions import DatabaseError
import logging

logger = logging.getLogger(__name__)


class InterviewRepository:
    def __init__(self):
        self.collection: AsyncIOMotorCollection = None
    
    async def _get_collection(self) -> AsyncIOMotorCollection:
        if self.collection is None:
            db = await MongoDB.get_database()
            self.collection = db.interviews
            
            # Create indexes
            await self.collection.create_index("phone_number")
            await self.collection.create_index("message_id", unique=True)
            await self.collection.create_index("created_at")
            await self.collection.create_index("status")
            
        return self.collection

    
    async def create(self, interview: Interview) -> Interview:
        try:
            collection = await self._get_collection()
            await collection.insert_one(interview.dict())
            
            logger.info("Interview created", extra={
                "interview_id": interview.id,
                "phone_number": interview.phone_number
            })
            
            return interview
            
        except Exception as e:
            logger.error("Failed to create interview", extra={
                "error": str(e),
                "interview_id": interview.id
            })
            raise DatabaseError(f"Failed to create interview: {str(e)}")
    
    async def get_by_id(self, interview_id: str) -> Optional[Interview]:
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"id": interview_id})
            return Interview(**data) if data else None
            
        except Exception as e:
            logger.error("Failed to get interview by ID", extra={
                "error": str(e),
                "interview_id": interview_id
            })
            return None
    
    async def get_by_message_id(self, message_id: str) -> Optional[Interview]:
        try:
            collection = await self._get_collection()
            data = await collection.find_one({"message_id": message_id})
            return Interview(**data) if data else None
            
        except Exception as e:
            logger.error("Failed to get interview by message ID", extra={
                "error": str(e),
                "message_id": message_id
            })
            return None
    
    async def update(self, interview: Interview) -> Interview:
        try:
            collection = await self._get_collection()
            result = await collection.update_one(
                {"id": interview.id},
                {"$set": interview.dict()}
            )
            
            if result.matched_count == 0:
                raise DatabaseError(f"Interview not found: {interview.id}")
            
            logger.info("Interview updated", extra={
                "interview_id": interview.id,
                "status": interview.status
            })
            
            return interview
            
        except Exception as e:
            logger.error("Failed to update interview", extra={
                "error": str(e),
                "interview_id": interview.id
            })
            raise DatabaseError(f"Failed to update interview: {str(e)}")
    
    async def get_recent_by_phone(
        self, 
        phone_number: str, 
        limit: int = 10
    ) -> List[Interview]:
        try:
            collection = await self._get_collection()
            cursor = collection.find(
                {"phone_number": phone_number}
            ).sort("created_at", -1).limit(limit)
            
            interviews = []
            async for doc in cursor:
                interviews.append(Interview(**doc))
            
            return interviews
            
        except Exception as e:
            logger.error("Failed to get recent interviews", extra={
                "error": str(e),
                "phone_number": phone_number
            })
            return []
    
    async def get_processing_count(self) -> int:
        try:
            collection = await self._get_collection()
            return await collection.count_documents({
                "status": {"$in": [
                    InterviewStatus.PROCESSING,
                    InterviewStatus.TRANSCRIBING,
                    InterviewStatus.ANALYZING
                ]}
            })
            
        except Exception as e:
            logger.error("Failed to get processing count", extra={
                "error": str(e)
            })
            return 0
