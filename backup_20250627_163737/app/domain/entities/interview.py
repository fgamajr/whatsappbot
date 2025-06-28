from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class InterviewStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class Interview(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    id: str = Field(default_factory=lambda: str(int(datetime.now().timestamp() * 1000)))
    phone_number: str
    message_id: str
    status: InterviewStatus = InterviewStatus.PENDING
    
    # Audio info
    audio_id: str
    audio_size_mb: float = 0.0
    duration_minutes: Optional[float] = None
    
    # Processing info
    chunks_total: int = 0
    chunks_processed: int = 0
    
    # Results
    transcript: Optional[str] = None
    analysis: Optional[str] = None
    
    # Files
    transcript_file_id: Optional[str] = None
    analysis_file_id: Optional[str] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
        
    def mark_processing(self):
        self.status = InterviewStatus.PROCESSING
        self.started_at = datetime.now()
    
    def mark_completed(self):
        self.status = InterviewStatus.COMPLETED
        self.completed_at = datetime.now()
    
    def mark_failed(self, error: str):
        self.status = InterviewStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()