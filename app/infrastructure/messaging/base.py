from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from enum import Enum


class MessageType(Enum):
    TEXT = "text"
    AUDIO = "audio"
    DOCUMENT = "document"


class MessagingProvider(ABC):
    """Abstract base class for messaging service providers"""
    
    @abstractmethod
    async def send_text_message(self, to: str, message: str) -> bool:
        """Send a text message"""
        pass
    
    @abstractmethod
    async def download_media(self, media_id: str) -> Optional[bytes]:
        """Download media file"""
        pass
    
    @abstractmethod
    async def upload_media(self, file_path: str) -> Optional[str]:
        """Upload media file and return media ID"""
        pass
    
    @abstractmethod
    async def edit_message(self, to: str, message_id: int, new_text: str) -> bool:
        """Edit an existing text message"""
        pass
    
    @abstractmethod
    async def send_video_message(self, to: str, video_data: bytes, filename: str) -> bool:
        """Send a video message"""
        pass
    
    @abstractmethod
    async def send_audio_message(self, to: str, audio_data: bytes, filename: str) -> bool:
        """Send an audio message"""
        pass
    
    @abstractmethod
    def extract_message_data(self, webhook_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract standardized message data from provider-specific webhook"""
        pass
    
    @abstractmethod
    def validate_webhook(self, request_data: Dict[str, Any], query_params: Dict[str, str]) -> bool:
        """Validate webhook request"""
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the provider name"""
        pass


class StandardMessage:
    """Standardized message format across all providers"""
    
    def __init__(self, from_number: str, message_type: MessageType, message_id: str, 
                 timestamp: Optional[str] = None, content: Optional[str] = None, 
                 media_id: Optional[str] = None):
        self.from_number = from_number
        self.message_type = message_type
        self.message_id = message_id
        self.timestamp = timestamp
        self.content = content
        self.media_id = media_id
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "from": self.from_number,
            "type": self.message_type.value,
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "content": self.content,
            "media_id": self.media_id
        }