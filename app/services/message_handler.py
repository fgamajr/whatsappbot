from typing import Dict, Any, Optional
import logging
from app.domain.entities.interview import Interview
from app.infrastructure.database.repositories.interview import InterviewRepository
from app.infrastructure.database.repositories.prompt import PromptRepository
from app.infrastructure.messaging.factory import get_messaging_service
from app.services.conversation_manager import ConversationManager
from app.tasks.pipeline_orchestrator import start_audio_processing
from app.tasks.analysis_tasks import start_analysis_pipeline
from app.core.config import settings

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self):
        self.convo_manager = ConversationManager()
        self.interview_repo = InterviewRepository()
        self.prompt_repo = PromptRepository()
        self.messaging_service = get_messaging_service()

    async def handle_message(self, message_data: Dict[str, Any]):
        """Main entry point to handle all incoming messages."""
        user_id = message_data.get('from')

        if message_data.get('type') == 'interactive_reply':
            await self._handle_interactive_reply(user_id, message_data)
        elif message_data.get('type') == 'text':
            await self._handle_text_message(user_id, message_data)
        elif message_data.get('type') in ['audio', 'voice']:
            await self._handle_audio_message(user_id, message_data)
        else:
            logger.warning(f"Unhandled message type: {message_data.get('type')}")

    async def _handle_audio_message(self, user_id: str, message_data: Dict[str, Any]):
        """Handles a new audio submission."""
        await self.messaging_service.send_text_message(
            to=user_id,
            text="\U0001F4C1 Áudio recebido! Iniciando processamento..."
        )
        start_audio_processing(message_data)

    async def _handle_text_message(self, user_id: str, message_data: Dict[str, Any]):
        """Handles a text message, likely a custom prompt."""
        state_info = self.convo_manager.get_state(user_id)
        if state_info and state_info.get("state") == "AWAITING_CUSTOM_PROMPT":
            interview_id = state_info["data"]["interview_id"]
            custom_prompt = message_data["text"]["body"]
            
            await self.messaging_service.send_text_message(
                to=user_id,
                text=f"\U0001F9E0 Ok, usando seu prompt personalizado para gerar a análise..."
            )
            
            start_analysis_pipeline(interview_id, custom_prompt)
            self.convo_manager.clear_state(user_id)
        else:
            await self.messaging_service.send_text_message(
                to=user_id,
                text="Olá! Por favor, envie um arquivo de áudio para iniciar."
            )

    async def _handle_interactive_reply(self, user_id: str, message_data: Dict[str, Any]):
        """Handles a reply from an interactive message (button click)."""
        reply_id = message_data["interactive"]["reply"]["id"]
        action, *params = reply_id.split(':')

        if action == "summarize":
            await self._request_prompt_selection(user_id, params[0])
        elif action == "end":
            await self.messaging_service.send_text_message(to=user_id, text="Ok, processo encerrado.")
            self.convo_manager.clear_state(user_id)
        elif action == "select_prompt":
            interview_id, prompt_name = params
            prompt = self.prompt_repo.get_prompt_by_name(prompt_name)
            if prompt:
                await self.messaging_service.send_text_message(to=user_id, text=f"\U0001F9E0 Entendido! Gerando análise com o prompt \"{prompt.name}\"...")
                start_analysis_pipeline(interview_id, prompt.text)
                self.convo_manager.clear_state(user_id)
        elif action == "custom_prompt":
            interview_id = params[0]
            self.convo_manager.set_state(user_id, "AWAITING_CUSTOM_PROMPT", {"interview_id": interview_id})
            await self.messaging_service.send_text_message(to=user_id, text="Por favor, digite e envie o prompt que você deseja usar.")

    async def _request_prompt_selection(self, user_id: str, interview_id: str):
        """Sends a message asking the user to select a prompt."""
        prompts = self.prompt_repo.get_active_prompts()
        
        buttons = []
        for p in prompts:
            buttons.append({"type": "reply", "title": p.name, "id": f"select_prompt:{interview_id}:{p.name}"})
        
        buttons.append({"type": "reply", "title": "✍️ Digitar Meu Próprio Prompt", "id": f"custom_prompt:{interview_id}"})

        await self.messaging_service.send_interactive_message(
            to=user_id,
            text="Selecione o tipo de análise:",
            buttons=buttons
        )
        self.convo_manager.set_state(user_id, "AWAITING_PROMPT_CHOICE", {"interview_id": interview_id})