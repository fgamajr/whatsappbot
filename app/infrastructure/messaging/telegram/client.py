import aiohttp
import os
from typing import Optional, Dict, Any, List
import logging
from app.core.config import settings
from app.infrastructure.messaging.base import MessagingProvider, MessageType, StandardMessage

logger = logging.getLogger(__name__)

class TelegramProvider(MessagingProvider):
    def __init__(self):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN não configurado.")
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    async def send_text_message(self, to: str, message: str) -> bool:
        url = f"{self.base_url}/sendMessage"
        payload = {"chat_id": to, "text": message, "parse_mode": "Markdown"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Message sent to {to}")
                    return True
                else:
                    logger.error(f"Failed to send message to {to}: {await response.text()}")
                    return False

    async def send_interactive_message(self, to: str, text: str, buttons: List[Dict[str, str]]) -> bool:
        """Sends a message with inline keyboard buttons."""
        inline_keyboard = [[{"text": b['title'], "callback_data": b['id']}] for b in buttons]]
        payload = {
            'chat_id': to,
            'text': text,
            'reply_markup': {'inline_keyboard': inline_keyboard},
            'parse_mode': 'Markdown'
        }
        url = f"{self.base_url}/sendMessage"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Interactive message sent to {to}")
                    return True
                else:
                    logger.error(f"Failed to send interactive message to {to}: {await response.text()}")
                    return False

    async def download_media(self, file_id: str) -> Optional[bytes]:
        """Downloads media using the file_id."""
        try:
            # 1. Get file path
            file_path_url = f"{self.base_url}/getFile?file_id={file_id}"
            async with aiohttp.ClientSession() as session:
                async with session.get(file_path_url) as response:
                    if response.status != 200:
                        logger.error(f"Failed to get file path for {file_id}: {await response.text()}")
                        return None
                    file_data = await response.json()
                    file_path = file_data['result']['file_path']

            # 2. Download the file
            file_download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            async with aiohttp.ClientSession() as session:
                async with session.get(file_download_url) as response:
                    if response.status == 200:
                        logger.info(f"Successfully downloaded media for file_id: {file_id}")
                        return await response.read()
                    else:
                        logger.error(f"Failed to download file {file_path}: {await response.text()}")
                        return None
        except Exception as e:
            logger.error(f"Exception during media download for {file_id}: {e}", exc_info=True)
            return None

    async def send_document(self, to: str, file_path: str, caption: str) -> bool:
        """Sends a document from a local file path."""
        url = f"{self.base_url}/sendDocument"
        data = aiohttp.FormData()
        data.add_field('chat_id', to)
        data.add_field('caption', caption)
        data.add_field('document', open(file_path, 'rb'), filename=os.path.basename(file_path))

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                if response.status == 200:
                    logger.info(f"Document {file_path} sent to {to}")
                    return True
                else:
                    logger.error(f"Failed to send document to {to}: {await response.text()}")
                    return False

    def extract_message_data(self, webhook_data: Dict[str, Any]) -> Optional[StandardMessage]:
        """Extracts standard message format from Telegram webhook data."""
        if "callback_query" in webhook_data:
            callback = webhook_data["callback_query"]
            user_id = str(callback["from"]["id"])
            return StandardMessage(
                from_number=user_id,
                message_type=MessageType.INTERACTIVE_REPLY,
                message_id=str(callback["id"]),
                timestamp=str(callback["message"]["date"]),
                content=callback["data"]
            )

        if "message" not in webhook_data:
            return None
        
        message = webhook_data["message"]
        user_id = str(message["chat"]["id"])
        message_id = str(message["message_id"])
        timestamp = str(message.get("date", ""))

        msg_type = MessageType.UNKNOWN
        content = None
        media_id = None

        if "text" in message:
            msg_type = MessageType.TEXT
            content = message["text"]
        elif message.get("voice") or message.get("audio"):
            msg_type = MessageType.AUDIO
            media_id = message.get("voice", {}).get("file_id") or message.get("audio", {}).get("file_id")
        
        if msg_type == MessageType.UNKNOWN:
            return None

        return StandardMessage(
            from_number=user_id,
            message_type=msg_type,
            message_id=message_id,
            timestamp=timestamp,
            content=content,
            media_id=media_id
        )

    def validate_webhook(self, request: Any, body: bytes) -> bool:
        # Telegram validation can be done via a secret token in the URL if needed
        # For now, we trust the source if the payload is valid JSON.
        return True
