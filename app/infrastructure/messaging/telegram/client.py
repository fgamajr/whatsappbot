import aiohttp
import os
from typing import Optional, Dict, Any
import logging
import traceback
from app.core.config import settings
from app.infrastructure.messaging.base import MessagingProvider, MessageType, StandardMessage

logger = logging.getLogger(__name__)


class TelegramProvider(MessagingProvider):
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        
    async def send_text_message(self, to: str, message: str) -> bool:
        """Send text message via Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            
            data = {
                "chat_id": to,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        logger.info("Text message sent", extra={
                            "chat_id": to,
                            "message_length": len(message)
                        })
                        return True
                    else:
                        error_text = await response.text()
                        logger.error("Failed to send text message", extra={
                            "status": response.status,
                            "error": error_text,
                            "chat_id": to
                        })
                        return False
                        
        except Exception as e:
            logger.error("Error sending text message", extra={
                "error": str(e),
                "chat_id": to
            })
            traceback.print_exc()
            return False
    
    async def download_media(self, media_id: str) -> Optional[bytes]:
        """Download media file from Telegram"""
        try:
            # First, get the file path
            url = f"{self.base_url}/getFile"
            params = {"file_id": media_id}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error("Failed to get file path", extra={
                            "file_id": media_id,
                            "status": response.status,
                            "error": error_text
                        })
                        return None
                    
                    file_data = await response.json()
                    if not file_data.get("ok"):
                        logger.error("Telegram API error", extra={
                            "file_id": media_id,
                            "error": file_data.get("description")
                        })
                        return None
                    
                    file_path = file_data["result"]["file_path"]
                
                # Download the actual file
                download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
                async with session.get(download_url) as response:
                    if response.status == 200:
                        content = await response.read()
                        logger.info("Media downloaded", extra={
                            "file_id": media_id,
                            "size_bytes": len(content)
                        })
                        return content
                    else:
                        error_text = await response.text()
                        logger.error("Failed to download media", extra={
                            "file_id": media_id,
                            "status": response.status,
                            "error": error_text
                        })
                        return None
                        
        except Exception as e:
            logger.error("Error downloading media", extra={
                "error": str(e),
                "file_id": media_id
            })
            traceback.print_exc()
            return None
    
    async def upload_media(self, file_path: str) -> Optional[str]:
        """Upload media file to Telegram (not needed for sending documents)"""
        # Telegram doesn't require separate upload step like WhatsApp
        # We'll return the file path as the "media_id" for consistency
        if os.path.exists(file_path):
            return file_path
        return None
    
    async def send_document(self, to: str, media_id: str, caption: str, filename: str) -> bool:
        """Send document message via Telegram"""
        try:
            url = f"{self.base_url}/sendDocument"
            
            # For Telegram, media_id is actually the file path
            file_path = media_id
            
            if not os.path.exists(file_path):
                logger.error("File not found", extra={"file_path": file_path})
                return False
            
            logger.info("Attempting to send document", extra={
                "chat_id": to,
                "file_path": file_path,
                "document_filename": filename,
                "caption_length": len(caption) if caption else 0
            })
            
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('chat_id', to)
                data.add_field('caption', caption)
                
                with open(file_path, 'rb') as f:
                    data.add_field('document', f, filename=filename)
                    
                    async with session.post(url, data=data) as response:
                        response_text = await response.text()
                        
                        if response.status == 200:
                            response_json = await response.json()
                            if response_json.get("ok"):
                                logger.info("Document sent successfully", extra={
                                    "chat_id": to,
                                    "file_path": file_path,
                                    "document_filename": filename
                                })
                                return True
                            else:
                                logger.error("Telegram API error", extra={
                                    "chat_id": to,
                                    "error": response_json.get("description"),
                                    "response": response_text
                                })
                                return False
                        else:
                            logger.error("Failed to send document", extra={
                                "status": response.status,
                                "error": response_text,
                                "chat_id": to,
                                "file_path": file_path
                            })
                            return False
                        
        except Exception as e:
            print("\n\n================================================")
            print(">>> ERRO INESPERADO DURANTE O ENVIO DO DOCUMENTO TELEGRAM <<<")
            traceback.print_exc()
            print("================================================\n\n")
            
            logger.error("Error sending document", extra={
                "error": str(e),
                "chat_id": to,
                "file_path": media_id
            })
            return False

    def extract_message_data(self, webhook_data: Dict[str, Any]) -> Optional[StandardMessage]:
        """Extract standardized message data from Telegram webhook"""
        try:
            message = webhook_data.get("message")
            if not message:
                return None
            
            message_id = str(message["message_id"])
            chat_id = str(message["chat"]["id"])
            timestamp = str(message.get("date", ""))
            
            # Check message type
            if "voice" in message:
                # Voice message
                message_type = MessageType.AUDIO
                media_id = message["voice"]["file_id"]
                content = None
            elif "audio" in message:
                # Audio file
                message_type = MessageType.AUDIO
                media_id = message["audio"]["file_id"]
                content = None
            elif "text" in message:
                # Text message
                message_type = MessageType.TEXT
                media_id = None
                content = message["text"]
            else:
                return None  # Unsupported message type
            
            return StandardMessage(
                from_number=chat_id,
                message_type=message_type,
                message_id=message_id,
                timestamp=timestamp,
                content=content,
                media_id=media_id
            )
            
        except (KeyError, TypeError) as e:
            logger.error("Error extracting Telegram message data", extra={
                "error": str(e)
            })
            return None

    def validate_webhook(self, request_data: Dict[str, Any], query_params: Dict[str, str]) -> bool:
        """Validate Telegram webhook request"""
        # Basic validation for Telegram webhook
        try:
            # Check if it's a message update
            if "message" in request_data:
                message = request_data["message"]
                return "chat" in message and "message_id" in message
            return False
            
        except (KeyError, TypeError):
            return False