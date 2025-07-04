import logging
import asyncio
from app.celery_app import celery_app
from app.core.config import settings
from app.infrastructure.messaging.factory import get_messaging_service
from app.infrastructure.database.repositories.interview import InterviewRepository

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.notify_user_for_next_action")
def notify_user_for_next_action(interview_data: dict):
    """
    Sends a message to the user with the generated title and interactive buttons
    to choose the next step (summarize or end).
    """
    interview_id = interview_data.get("interview_id")
    if not interview_id:
        logger.error("Interview ID not found in data for notification.")
        return

    try:
        interview_repo = InterviewRepository()
        interview = interview_repo.get_interview_by_id(interview_id)

        if not interview:
            logger.error(f"Interview {interview_id} not found for notification.")
            return

        title = interview.title or "Áudio Processado"
        phone_number = interview.phone_number

        messaging_service = get_messaging_service()

        message_text = f'\U0001F3A5 **Áudio Processado:**\n_"{title}"_\n\nO que você gostaria de fazer?'

        buttons = [
            {"type": "reply", "title": "✅ Resumir Agora", "id": f"summarize:{interview_id}"},
            {"type": "reply", "title": "⏹️ Encerrar", "id": f"end:{interview_id}"}
        ]

        async def send_message_async():
            await messaging_service.send_interactive_message(
                to=phone_number,
                text=message_text,
                buttons=buttons
            )

        asyncio.run(send_message_async())

        logger.info(f"Sent next action prompt to user for interview {interview_id}")

    except Exception as e:
        logger.error(f"Failed to send next action notification for interview {interview_id}: {e}", exc_info=True)
