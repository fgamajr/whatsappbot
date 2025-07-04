from typing import Optional, List, Dict, Any
from pymongo import MongoClient
from bson.objectid import ObjectId
from app.domain.entities.interview import Interview, InterviewStatus
from app.core.config import settings
from app.core.exceptions import DatabaseError
import logging

logger = logging.getLogger(__name__)

class InterviewRepository:
    _instance = None
    _client = None
    _db = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(InterviewRepository, cls).__new__(cls)
            try:
                cls._client = MongoClient(settings.MONGODB_URL)
                cls._db = cls._client[settings.DB_NAME]
                logger.info("MongoDB connection established for InterviewRepository.")
                # Create indexes on first instantiation
                cls._create_indexes(cls._db.interviews)
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {e}", exc_info=True)
                cls._instance = None # Prevent returning a broken instance
                raise DatabaseError(f"Failed to connect to MongoDB: {e}")
        return cls._instance

    @classmethod
    def _create_indexes(cls, collection):
        try:
            collection.create_index("phone_number")
            collection.create_index("message_id", unique=True)
            collection.create_index([("created_at", -1)])
            collection.create_index("status")
            logger.info("Indexes created for interviews collection.")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}", exc_info=True)

    @property
    def collection(self):
        return self._db.interviews

    def create_interview(self, interview: Interview) -> Interview:
        try:
            interview_dict = interview.model_dump(by_alias=True)
            result = self.collection.insert_one(interview_dict)
            interview.id = str(result.inserted_id)
            logger.info(f"Interview created with ID: {interview.id}")
            return interview
        except Exception as e:
            logger.error(f"Failed to create interview: {e}", exc_info=True)
            raise DatabaseError(f"Failed to create interview: {e}")

    def get_interview_by_id(self, interview_id: str) -> Optional[Interview]:
        try:
            document = self.collection.find_one({"_id": ObjectId(interview_id)})
            if document:
                return Interview(**document)
            return None
        except Exception as e:
            logger.error(f"Failed to get interview by ID {interview_id}: {e}", exc_info=True)
            return None

    def update_interview(self, interview_id: str, update_data: Dict[str, Any]) -> bool:
        try:
            result = self.collection.update_one(
                {"_id": ObjectId(interview_id)},
                {"$set": update_data}
            )
            if result.matched_count == 0:
                logger.warning(f"Interview not found for update: {interview_id}")
                return False
            logger.info(f"Interview {interview_id} updated successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to update interview {interview_id}: {e}", exc_info=True)
            return False

    def get_by_message_id(self, message_id: str) -> Optional[Interview]:
        try:
            document = self.collection.find_one({"message_id": message_id})
            if document:
                return Interview(**document)
            return None
        except Exception as e:
            logger.error(f"Failed to get interview by message_id {message_id}: {e}", exc_info=True)
            return None
