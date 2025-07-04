from pydantic import BaseModel, Field
from typing import Optional
import datetime

class Prompt(BaseModel):
    """
    Represents a prompt entity in the system.
    """
    id: Optional[str] = Field(None, alias="_id")
    name: str = Field(..., description="A unique name for the prompt, e.g., 'interview_summary_v1'.")
    text: str = Field(..., description="The full text of the prompt.")
    version: int = Field(1, description="The version of the prompt.")
    is_active: bool = Field(False, description="Indicates if this is the default prompt to be used.")
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "name": "interview_summary_v1",
                "text": "Summarize the following interview transcript...",
                "version": 1,
                "is_active": True,
            }
        }
