import aiohttp
import os
from typing import Optional
import logging
import traceback
from app.core.config import settings
from app.core.exceptions import WhatsAppError

logger = logging.getLogger(__name__)


class WhatsAppClient:
    def __init__(self):
        self.token = settings.WHATSAPP_TOKEN
        self.phone_number_id = settings.PHONE_NUMBER_ID
        self.api_version = settings.WHATSAPP_API_VERSION
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        
    async def send_text_message(self, to_number: str, message: str) -> bool:
        """Send text message via WhatsApp"""
        try:
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {"body": message}
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status == 200:
                        logger.info("Text message sent", extra={
                            "to_number": to_number,
                            "message_length": len(message)
                        })
                        return True
                    else:
                        error_text = await response.text()
                        logger.error("Failed to send text message", extra={
                            "status": response.status,
                            "error": error_text,
                            "to_number": to_number
                        })
                        return False
                        
        except Exception as e:
            logger.error("Error sending text message", extra={
                "error": str(e),
                "to_number": to_number
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
    
    async def send_document(self, to_number: str, media_id: str, caption: str, filename: str) -> bool:
        """Send document message via WhatsApp"""
        try:
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "document",
                "document": {
                    "id": media_id,
                    "caption": caption,
                    "filename": filename
                }
            }
            
            logger.info("Attempting to send document", extra={
                "to_number": to_number,
                "media_id": media_id,
                "document_filename": filename,
                "caption_length": len(caption) if caption else 0
            })
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        logger.info("Document sent successfully", extra={
                            "to_number": to_number,
                            "media_id": media_id,
                            "document_filename": filename
                        })
                        return True
                    else:
                        logger.error("Failed to send document", extra={
                            "status": response.status,
                            "error": response_text,
                            "to_number": to_number,
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
                "to_number": to_number,
                "media_id": media_id
            })
            return False