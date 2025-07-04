from typing import List, Optional
from app.domain.entities.prompt import Prompt
from app.infrastructure.database.mongodb import get_database
from app.core.config import settings
from motor.motor_asyncio import AsyncIOMotorDatabase

class PromptRepository:
    """
    Repository for handling CRUD operations for Prompts.
    """

    def __init__(self):
        self.db: AsyncIOMotorDatabase = get_database()
        self.collection = self.db.get_collection("prompts")

    async def create_prompt(self, prompt: Prompt) -> Prompt:
        """Creates a new prompt in the database."""
        prompt_dict = prompt.model_dump(by_alias=True, exclude=["id"])
        result = await self.collection.insert_one(prompt_dict)
        prompt.id = str(result.inserted_id)
        return prompt

    async def get_prompt_by_name(self, name: str) -> Optional[Prompt]:
        """Retrieves a prompt by its name."""
        document = await self.collection.find_one({"name": name})
        if document:
            return Prompt(**document)
        return None

    async def get_active_prompts(self) -> List[Prompt]:
        """Retrieves all active prompts."""
        prompts = []
        cursor = self.collection.find({"is_active": True}).sort("name", 1)
        async for document in cursor:
            prompts.append(Prompt(**document))
        return prompts

    async def get_all_prompts(self) -> List[Prompt]:
        """Retrieves all prompts from the database."""
        prompts = []
        cursor = self.collection.find({}).sort("name", 1)
        async for document in cursor:
            prompts.append(Prompt(**document))
        return prompts
