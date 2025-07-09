import aiohttp
import os
import tempfile
from typing import Optional, Dict, Any
import logging
import traceback
from app.core.config import settings
from app.core.exceptions import WhatsAppError
from app.infrastructure.messaging.base import MessagingProvider, MessageType, StandardMessage
from app.domain.value_objects.phone_number import BrazilianPhoneNumber

logger = logging.getLogger(__name__)


class WhatsAppProvider(MessagingProvider):
    def __init__(self):
        self.token = settings.WHATSAPP_TOKEN
        self.phone_number_id = settings.PHONE_NUMBER_ID
        self.api_version = settings.WHATSAPP_API_VERSION
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
    
    def get_provider_name(self) -> str:
        """Get the provider name"""
        return "whatsapp"
        
    async def send_text_message(self, to: str, message: str) -> bool:
        """Send text message via WhatsApp"""
        try:
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": message}
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status == 200:
                        logger.info("Text message sent", extra={
                            "to_number": to,
                            "message_length": len(message)
                        })
                        return True
                    else:
                        error_text = await response.text()
                        logger.error("Failed to send text message", extra={
                            "status": response.status,
                            "error": error_text,
                            "to_number": to
                        })
                        return False
                        
        except Exception as e:
            logger.error("Error sending text message", extra={
                "error": str(e),
                "to_number": to
            })
            traceback.print_exc()
            return False
    
    async def download_media(self, media_id: str) -> Optional[bytes]:
        """Download media file from WhatsApp"""
        try:
            # First, get the media URL
            url = f"{self.base_url}/{media_id}"
            headers = {"Authorization": f"Bearer {self.token}"}
            
            async with aiohttp.ClientSession() as session:
                # Get media URL
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error("Failed to get media URL", extra={
                            "media_id": media_id,
                            "status": response.status,
                            "error": error_text
                        })
                        return None
                    
                    media_data = await response.json()
                    media_url = media_data.get("url")
                    
                    if not media_url:
                        logger.error("No media URL in response", extra={
                            "media_id": media_id,
                            "response_data": media_data
                        })
                        return None
                
                # Download the actual media file
                async with session.get(media_url, headers=headers) as response:
                    if response.status == 200:
                        content = await response.read()
                        logger.info("Media downloaded", extra={
                            "media_id": media_id,
                            "size_bytes": len(content)
                        })
                        return content
                    else:
                        error_text = await response.text()
                        logger.error("Failed to download media", extra={
                            "media_id": media_id,
                            "status": response.status,
                            "error": error_text
                        })
                        return None
                        
        except Exception as e:
            logger.error("Error downloading media", extra={
                "error": str(e),
                "media_id": media_id
            })
            traceback.print_exc()
            return None
    
    async def upload_media(self, file_path: str) -> Optional[str]:
        """Upload media file to WhatsApp using aiohttp"""
        try:
            url = f"{self.base_url}/{self.phone_number_id}/media"
            headers = {"Authorization": f"Bearer {self.token}"}
            
            # Verificar se o arquivo existe
            if not os.path.exists(file_path):
                logger.error("File not found", extra={"file_path": file_path})
                return None
            
            file_name = os.path.basename(file_path)
            
            # Determinar o MIME type baseado na extensão do arquivo
            mime_type_map = {
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.pdf': 'application/pdf',
                '.txt': 'text/plain',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.mp3': 'audio/mpeg',
                '.mp4': 'video/mp4',
                '.wav': 'audio/wav',
                '.ogg': 'audio/ogg'
            }
            
            file_extension = os.path.splitext(file_path)[1].lower()
            mime_type = mime_type_map.get(file_extension, 'application/octet-stream')
            
            # Usar aiohttp para upload assíncrono
            async with aiohttp.ClientSession() as session:
                # Criar o FormData para multipart/form-data
                data = aiohttp.FormData()
                
                # Adicionar campos de metadados
                data.add_field('messaging_product', 'whatsapp')
                data.add_field('type', 'document')
                
                # Adicionar o arquivo
                with open(file_path, 'rb') as f:
                    data.add_field('file', f, filename=file_name, content_type=mime_type)
                    
                    async with session.post(url, headers=headers, data=data) as response:
                        response_text = await response.text()
                        
                        if response.status == 200:
                            try:
                                response_json = await response.json()
                                media_id = response_json.get("id")
                                
                                if media_id:
                                    logger.info("Media uploaded successfully", extra={
                                        "file_path": file_path,
                                        "media_id": media_id,
                                        "file_size": os.path.getsize(file_path),
                                        "mime_type": mime_type
                                    })
                                    return media_id
                                else:
                                    logger.error("No media ID in response", extra={
                                        "file_path": file_path,
                                        "response": response_text
                                    })
                                    return None
                                    
                            except Exception as json_error:
                                logger.error("Failed to parse JSON response", extra={
                                    "file_path": file_path,
                                    "response": response_text,
                                    "json_error": str(json_error)
                                })
                                return None
                        else:
                            logger.error("Failed to upload media", extra={
                                "file_path": file_path,
                                "status": response.status,
                                "response": response_text
                            })
                            return None
                        
        except Exception as e:
            print("\n\n================================================")
            print(">>> ERRO INESPERADO DURANTE O UPLOAD PARA WHATSAPP <<<")
            traceback.print_exc()
            print("================================================\n\n")
            
            logger.error("Error uploading media", extra={
                "error": str(e),
                "file_path": file_path
            })
            return None
    
    async def send_document(self, to: str, media_id: str, caption: str, filename: str) -> bool:
        """Send document message via WhatsApp"""
        try:
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "document",
                "document": {
                    "id": media_id,
                    "caption": caption,
                    "filename": filename
                }
            }
            
            logger.info("Attempting to send document", extra={
                "to_number": to,
                "media_id": media_id,
                "document_filename": filename,
                "caption_length": len(caption) if caption else 0
            })
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        logger.info("Document sent successfully", extra={
                            "to_number": to,
                            "media_id": media_id,
                            "document_filename": filename
                        })
                        return True
                    else:
                        logger.error("Failed to send document", extra={
                            "status": response.status,
                            "error": response_text,
                            "to_number": to,
                            "media_id": media_id,
                            "request_data": data
                        })
                        return False
                        
        except Exception as e:
            print("\n\n================================================")
            print(">>> ERRO INESPERADO DURANTE O ENVIO DO DOCUMENTO <<<")
            traceback.print_exc()
            print("================================================\n\n")
            
            logger.error("Error sending document", extra={
                "error": str(e),
                "to_number": to,
                "media_id": media_id
            })
            return False
    
    async def send_video_message(self, to: str, video_data: bytes, filename: str) -> bool:
        """Send a video message via WhatsApp"""
        try:
            # Create temporary file for video
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
                temp_file.write(video_data)
                temp_file_path = temp_file.name
            
            try:
                # Upload the video
                media_id = await self.upload_media(temp_file_path)
                if not media_id:
                    logger.error("Failed to upload video", extra={
                        "to_number": to,
                        "filename": filename,
                        "size_bytes": len(video_data)
                    })
                    return False
                
                # Send as document with video MIME type
                success = await self.send_document(
                    to=to,
                    media_id=media_id,
                    caption=f"📹 {filename}",
                    filename=filename
                )
                
                logger.info("Video message sent", extra={
                    "to_number": to,
                    "filename": filename,
                    "size_bytes": len(video_data),
                    "media_id": media_id,
                    "success": success
                })
                
                return success
                
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
                    
        except Exception as e:
            logger.error("Error sending video message", extra={
                "error": str(e),
                "to_number": to,
                "filename": filename,
                "size_bytes": len(video_data)
            })
            return False
    
    async def send_audio_message(self, to: str, audio_data: bytes, filename: str) -> bool:
        """Send an audio message via WhatsApp"""
        try:
            # Create temporary file for audio
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            try:
                # Upload the audio
                media_id = await self.upload_media(temp_file_path)
                if not media_id:
                    logger.error("Failed to upload audio", extra={
                        "to_number": to,
                        "filename": filename,
                        "size_bytes": len(audio_data)
                    })
                    return False
                
                # Send as document with audio MIME type
                success = await self.send_document(
                    to=to,
                    media_id=media_id,
                    caption=f"🎵 {filename}",
                    filename=filename
                )
                
                logger.info("Audio message sent", extra={
                    "to_number": to,
                    "filename": filename,
                    "size_bytes": len(audio_data),
                    "media_id": media_id,
                    "success": success
                })
                
                return success
                
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass
                    
        except Exception as e:
            logger.error("Error sending audio message", extra={
                "error": str(e),
                "to_number": to,
                "filename": filename,
                "size_bytes": len(audio_data)
            })
            return False

    def extract_message_data(self, webhook_data: Dict[str, Any]) -> Optional[StandardMessage]:
        """Extract standardized message data from WhatsApp webhook"""
        try:
            messages = webhook_data["entry"][0]["changes"][0]["value"]["messages"][0]
            
            message_id = messages["id"]
            message_type_str = messages["type"]
            from_number = messages["from"]
            timestamp = messages.get("timestamp")
            
            # Validate and fix phone number
            try:
                phone = BrazilianPhoneNumber(number=from_number)
                from_number = phone.number
            except:
                pass  # Use original number if validation fails
            
            # Convert to standard message type
            if message_type_str == "audio":
                message_type = MessageType.AUDIO
                media_id = messages["audio"]["id"]
                content = None
            elif message_type_str == "text":
                message_type = MessageType.TEXT
                media_id = None
                content = messages["text"]["body"]
            else:
                return None  # Unsupported message type
            
            return StandardMessage(
                from_number=from_number,
                message_type=message_type,
                message_id=message_id,
                timestamp=timestamp,
                content=content,
                media_id=media_id
            )
            
        except (KeyError, IndexError) as e:
            logger.error("Error extracting WhatsApp message data", extra={
                "error": str(e)
            })
            return None

    def validate_webhook(self, request_data: Dict[str, Any], query_params: Dict[str, str]) -> bool:
        """Validate WhatsApp webhook request"""
        # For verification requests
        if query_params.get("hub.mode") == "subscribe":
            return query_params.get("hub.verify_token") == settings.WHATSAPP_VERIFY_TOKEN
        
        # For message webhooks, check if it contains valid message data
        try:
            entry = request_data.get("entry", [])
            if not entry:
                return False
                
            changes = entry[0].get("changes", [])
            if not changes:
                return False
                
            value = changes[0].get("value", {})
            
            # Ignore status updates
            if "statuses" in value:
                return False
            
            # Check for messages
            messages = value.get("messages", [])
            return bool(messages)
            
        except (IndexError, KeyError):
            return False