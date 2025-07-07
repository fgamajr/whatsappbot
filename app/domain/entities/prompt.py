from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class PromptCategory(str, Enum):
    INTERVIEW_ANALYSIS = "interview_analysis"
    TRANSCRIPTION_SUMMARY = "transcription_summary"
    CONTENT_EXTRACTION = "content_extraction"
    CUSTOM = "custom"


class PromptStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"


class PromptTemplate(BaseModel):
    """Domain entity for AI prompt templates"""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8] + str(int(datetime.now().timestamp()))[-6:])
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    category: PromptCategory
    status: PromptStatus = PromptStatus.ACTIVE
    
    # Prompt content
    prompt_text: str = Field(..., min_length=10)
    variables: List[str] = Field(default_factory=list)  # Variables like {transcript}, {language}
    
    # Metadata
    version: int = Field(default=1)
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Usage tracking
    usage_count: int = Field(default=0)
    last_used_at: Optional[datetime] = None
    
    # Configuration
    settings: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    
    # User interface
    display_order: int = Field(default=0)
    emoji: Optional[str] = None
    short_code: Optional[str] = None  # e.g., "entrevista", "resumo"
    
    def mark_used(self):
        """Mark prompt as used and update counters"""
        self.usage_count += 1
        self.last_used_at = datetime.now()
        self.updated_at = datetime.now()
    
    def is_active(self) -> bool:
        """Check if prompt is active and usable"""
        return self.status == PromptStatus.ACTIVE
    
    def get_variables_from_text(self) -> List[str]:
        """Extract variables from prompt text (e.g., {transcript}, {language})"""
        import re
        pattern = r'\{([^}]+)\}'
        return list(set(re.findall(pattern, self.prompt_text)))
    
    def format_prompt(self, **kwargs) -> str:
        """Format prompt with provided variables"""
        try:
            return self.prompt_text.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing required variable: {e}")
    
    def to_user_display(self) -> str:
        """Generate user-friendly display text"""
        emoji = self.emoji or "📝"
        return f"{emoji} {self.name} - {self.description}"
    
    def update(self, **kwargs):
        """Update prompt fields and timestamp"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now()


class UserPromptPreference(BaseModel):
    """Track user's prompt preferences"""
    
    user_id: str  # phone number or user identifier
    default_prompt_id: Optional[str] = None
    last_selected_prompt_id: Optional[str] = None
    preferred_category: Optional[PromptCategory] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)