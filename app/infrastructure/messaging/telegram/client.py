import aiohttp
import os
import tempfile
from typing import Optional, Dict, Any
import logging
import traceback
from telethon import TelegramClient
from telethon.tl.types import DocumentAttributeFilename

from app.core.config import settings
from app.infrastructure.messaging.base import MessagingProvider, MessageType, StandardMessage

logger = logging.getLogger(__name__)

_telethon_client = None

async def get_telethon_client():
    global _telethon_client
    if _telethon_client is None:
        if not all([settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH, settings.TELEGRAM_BOT_TOKEN]):
            logger.error("Credenciais do Telegram (API_ID, API_HASH, BOT_TOKEN) não configuradas.")
            return None
        _telethon_client = TelegramClient('bot', settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
    
    if not _telethon_client.is_connected():
        await _telethon_client.connect()

    if not await _telethon_client.is_user_authorized():
        await _telethon_client.start(bot_token=settings.TELEGRAM_BOT_TOKEN)
        
    return _telethon_client


class TelegramProvider(MessagingProvider):
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"
    
    def get_provider_name(self) -> str:
        """Get the provider name"""
        return "telegram"

    async def send_text_message(self, to: str, message: str) -> bool:
        try:
            client = await get_telethon_client()
            if not client: return False
            await client.send_message(int(to), message, parse_mode='md')
            logger.info("Text message sent via Telethon", extra={"chat_id": to})
            return True
        except Exception as e:
            logger.error("Failed to send text message via Telethon", extra={"error": str(e), "chat_id": to})
            return False

    async def download_media(self, media_payload: Any) -> Optional[bytes]:
        """Baixa mídia usando o objeto de mensagem real do Telethon ou dados do YouTube."""
        try:
            # Check if this is YouTube video data
            if isinstance(media_payload, dict) and media_payload.get("source") == "youtube":
                logger.info("Processing YouTube video data...")
                video_data = media_payload.get("video_data")
                if video_data:
                    logger.info("YouTube video data retrieved", extra={"size_bytes": len(video_data)})
                    return video_data
                else:
                    logger.error("No video data found in YouTube payload")
                    return None
            
            # Original Telegram media download logic
            client = await get_telethon_client()
            if not client:
                raise Exception("Cliente Telethon não pôde ser inicializado.")

            logger.info("Downloading media via Telethon...")
            
            # ---> INÍCIO DA CORREÇÃO <---
            
            # Extraímos o chat_id e message_id do dicionário que recebemos
            chat_id = int(media_payload['chat']['id'])
            message_id = int(media_payload['message_id'])

            # Usamos o cliente para buscar o objeto de mensagem real
            logger.info(f"Buscando mensagem original: chat={chat_id}, msg_id={message_id}")
            message = await client.get_messages(chat_id, ids=message_id)

            if not message or not message.media:
                logger.error("Não foi possível buscar a mensagem ou a mensagem não contém mídia.", extra={"chat_id": chat_id, "message_id": message_id})
                return None

            # Agora fazemos o download usando o objeto de mensagem, não o dicionário
            buffer = await client.download_media(message.media, file=bytes)
            
            # ---> FIM DA CORREÇÃO <---

            if buffer:
                logger.info("Media downloaded successfully via Telethon", extra={"size_bytes": len(buffer)})
                return buffer
            else:
                logger.warning("Telethon download_media retornou None.", extra={"payload": media_payload})
                return None

        except Exception as e:
            logger.error("Error downloading media with Telethon", extra={"error": str(e)})
            traceback.print_exc()
            raise Exception(f"Falha no download do arquivo via Telegram: {e}")

    async def upload_media(self, file_path: str) -> Optional[str]:
        if os.path.exists(file_path):
            return file_path
        return None
    
    async def edit_message(self, to: str, message_id: int, new_text: str) -> bool:
        """Edit an existing text message"""
        try:
            client = await get_telethon_client()
            if not client: return False
            await client.edit_message(int(to), message_id, new_text, parse_mode='md')
            return True
        except Exception as e:
            # Don't log errors for message not modified, it's common
            if "message not modified" not in str(e).lower():
                logger.warning("Failed to edit message", extra={"error": str(e)})
            return False
    
    async def send_video_message(self, to: str, video_data: bytes, filename: str) -> bool:
        """Send a video message via Telegram from bytes"""
        try:
            print(f"--- DEBUG: ENTERING send_video_message for chat {to} ---")
            print(f"--- DEBUG: Video data size: {len(video_data)} bytes ---")
            print(f"--- DEBUG: Filename: {filename} ---")

            client = await get_telethon_client()
            if not client:
                print("--- DEBUG: FAILED to get Telethon client ---")
                logger.error("Failed to get Telegram client")
                return False

            print("--- DEBUG: Got Telethon client, attempting to send file... ---")
            await client.send_file(
                int(to),
                file=video_data,
                caption=f"📹 {filename}",
                attributes=[DocumentAttributeFilename(file_name=filename)]
            )
            
            print("--- DEBUG: send_file call completed successfully. ---")
            logger.info("Video message sent via Telegram", extra={
                "chat_id": to,
                "file_name": filename,
                "size_bytes": len(video_data)
            })
            return True
        except Exception as e:
            import traceback
            print(f"---!!! ERROR in send_video_message for chat {to} !!!---")
            print(f"--- DEBUG: ERROR TYPE: {type(e).__name__}")
            print(f"--- DEBUG: ERROR DETAILS: {e}")
            print("--- TRACEBACK ---")
            traceback.print_exc()
            print("----------------------------------------------------")
            logger.error("Error sending video message via Telegram", extra={
                "error": str(e),
                "error_type": type(e).__name__,
            }, exc_info=True)
            return False
    
    async def send_audio_message(self, to: str, audio_data: bytes, filename: str) -> bool:
        """Send an audio message via Telegram from bytes"""
        try:
            client = await get_telethon_client()
            if not client:
                logger.error("Failed to get Telegram client")
                return False

            await client.send_file(
                int(to),
                file=audio_data,
                caption=f"🎵 {filename}",
                attributes=[DocumentAttributeFilename(file_name=filename)]
            )
            
            logger.info("Audio message sent via Telegram", extra={
                "chat_id": to,
                "media_filename": filename,
                "size_bytes": len(audio_data)
            })
            return True
        except Exception as e:
            logger.error("Error sending audio message via Telegram", extra={
                "error": str(e),
                "error_type": type(e).__name__,
            }, exc_info=True)
            return False

    async def send_document(self, to: str, file_path: str, caption: str, filename: str) -> bool:
        """Send a document file via Telegram"""
        try:
            client = await get_telethon_client()
            if not client:
                logger.error("Failed to get Telegram client")
                return False
            
            # Check if file exists
            import os
            if not os.path.exists(file_path):
                logger.error("Document file not found", extra={"file_path": file_path})
                return False
            
            # Send document file
            await client.send_file(
                int(to), 
                file_path,
                caption=caption,
                force_document=True  # Send as document, not as media
            )
            
            file_size = os.path.getsize(file_path)
            logger.info("Document sent via Telegram", extra={
                "chat_id": to,
                "document_filename": filename,
                "file_path": file_path,
                "file_size": file_size,
                "caption": caption
            })
            return True
                
        except Exception as e:
            logger.error("Failed to send document via Telegram", extra={
                "error": str(e),
                "chat_id": to,
                "document_filename": filename,
                "file_path": file_path
            })
            return False

    def extract_message_data(self, webhook_data: Dict[str, Any]) -> Optional[StandardMessage]:
        """Passa o objeto de mensagem inteiro para ser usado pelo download_media."""
        try:
            message_obj = webhook_data.get("message")
            if not message_obj:
                return None
            
            message_id = str(message_obj["message_id"])
            chat_id = str(message_obj["chat"]["id"])
            timestamp = str(message_obj.get("date", ""))
            
            if "voice" in message_obj or "audio" in message_obj or "video" in message_obj or "document" in message_obj:
                message_type = MessageType.AUDIO
                content = None
                media_payload = message_obj 
            elif "text" in message_obj:
                message_type = MessageType.TEXT
                content = message_obj["text"]
                media_payload = None
            else:
                return None
            
            return StandardMessage(
                from_number=chat_id,
                message_type=message_type,
                message_id=message_id,
                timestamp=timestamp,
                content=content,
                media_id=media_payload
            )
        except (KeyError, TypeError) as e:
            logger.error("Error extracting Telegram message data", extra={"error": str(e)})
            return None

    def validate_webhook(self, request_data: Dict[str, Any], query_params: Dict[str, str]) -> bool:
        try:
            if "message" in request_data:
                message = request_data["message"]
                return "chat" in message and "message_id" in message
            return False
        except (KeyError, TypeError):
            return False