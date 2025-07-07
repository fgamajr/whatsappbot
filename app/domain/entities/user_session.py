from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class SessionState(str, Enum):
    IDLE = "idle"
    WAITING_CUSTOM_INSTRUCTIONS = "waiting_custom_instructions"
    WAITING_AUDIO = "waiting_audio"


class UserSession(BaseModel):
    """Manages user interaction state for multi-step flows"""
    
    user_id: str
    state: SessionState = SessionState.IDLE
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime = Field(default_factory=lambda: datetime.now() + timedelta(minutes=30))
    
    def is_expired(self) -> bool:
        """Check if session has expired"""
        return datetime.now() > self.expires_at
    
    def extend_session(self, minutes: int = 30):
        """Extend session expiration time"""
        self.expires_at = datetime.now() + timedelta(minutes=minutes)
        self.updated_at = datetime.now()
    
    def set_state(self, state: SessionState, context: Optional[Dict[str, Any]] = None):
        """Update session state and context"""
        self.state = state
        if context:
            self.context.update(context)
        self.updated_at = datetime.now()
        self.extend_session()  # Extend on activity
    
    def clear_state(self):
        """Reset session to idle state"""
        self.state = SessionState.IDLE
        self.context.clear()
        self.updated_at = datetime.now()
    
    def get_context_value(self, key: str, default: Any = None) -> Any:
        """Get value from session context"""
        return self.context.get(key, default)