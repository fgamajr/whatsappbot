import aiohttp
import os
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
        """Baixa mídia usando o objeto de mensagem real do Telethon."""
        try:
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
    
    async def send_document(self, to: str, media_id: str, caption: str, filename: str) -> bool:
        try:
            client = await get_telethon_client()
            if not client: return False
            
            await client.send_file(
                int(to),
                file=media_id,
                caption=caption,
                attributes=[DocumentAttributeFilename(file_name=filename)]
            )
            logger.info("Document sent successfully via Telethon", extra={"chat_id": to, "filename": filename})
            return True
        except Exception as e:
            logger.error("Failed to send document via Telethon", extra={"error": str(e)})
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