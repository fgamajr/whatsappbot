from fastapi import APIRouter, Request, Response, BackgroundTasks
from typing import Dict, Any, Set
import logging
from app.services.message_handler import MessageHandler
from app.infrastructure.messaging.factory import get_messaging_service
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

processed_messages: Set[str] = set()

@router.post("/{provider_name}")
async def handle_webhook(provider_name: str, request: Request, background_tasks: BackgroundTasks):
    """Generic webhook handler for any messaging provider."""
    try:
        provider = get_messaging_service(provider_name)
        body = await request.body()
        
        # The validation logic might need the raw body
        if not provider.validate_webhook(request, body):
            logger.warning(f"Webhook validation failed for {provider_name}.")
            return Response(status_code=403)

        data = await request.json()
        standard_message = provider.extract_message_data(data)

        if not standard_message:
            logger.info(f"Could not extract standard message from {provider_name} payload.")
            return Response(status_code=200)

        # Duplicate check
        message_id = standard_message.message_id
        if message_id in processed_messages:
            logger.info(f"Duplicate message ignored: {message_id}")
            return Response(status_code=200)
        processed_messages.add(message_id)
        if len(processed_messages) > settings.MAX_CACHE_SIZE:
            processed_messages.clear()

        # Delegate all handling to the MessageHandler
        handler = MessageHandler()
        background_tasks.add_task(handler.handle_message, standard_message.to_dict())

        logger.info(f"Message from {provider_name} queued for handling.", extra={
            "message_id": message_id,
            "from": standard_message.from_number
        })

        return Response(status_code=200)

    except Exception as e:
        logger.error(f"Webhook processing error for {provider_name}", extra={"error": str(e)}, exc_info=True)
        return Response(status_code=500)
