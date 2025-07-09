from typing import Dict, Any
import logging
import os
import asyncio
from app.domain.entities.interview import Interview, InterviewStatus
from app.domain.entities.prompt import PromptCategory
from app.infrastructure.database.repositories.interview import InterviewRepository
from app.infrastructure.messaging.base import MessagingProvider
from app.services.audio_processor import AudioProcessor
from app.services.transcription import TranscriptionService
from app.services.analysis import AnalysisService
from app.services.document_generator import DocumentGenerator
from app.services.prompt_manager import PromptManagerService
from app.services.user_session_manager import UserSessionManager
from app.utils.progress_tracker import ProgressTracker
from app.core.config import settings

logger = logging.getLogger(__name__)


class MessageHandler:
    def __init__(self, provider: MessagingProvider):
        self.provider = provider
        self.interview_repo = InterviewRepository()
        self.audio_processor = AudioProcessor(settings.AUDIO_CHUNK_MINUTES)
        self.transcription_service = TranscriptionService()
        self.analysis_service = AnalysisService()
        self.doc_generator = DocumentGenerator()

    async def process_audio_message(self, message_data: Dict):
        """High-level wrapper for audio processing with state management."""
        from_number = message_data["from"]
        session_manager = UserSessionManager()
        interview = None
        
        try:
            # Set user to busy state
            await session_manager.set_user_busy(from_number, "Processando áudio")

            # Create and process the interview
            interview = await self._create_and_process_interview(message_data)

        except Exception as e:
            logger.error(f"Erro fatal no processamento da entrevista: {e}", extra={"interview_id": interview.id if interview else "N/A"})
            if interview:
                interview.status = InterviewStatus.FAILED
                await self.interview_repo.update(interview)
            await self.provider.send_text_message(
                from_number,
                "❌ Ocorreu um erro grave ao processar seu áudio. A equipe de suporte foi notificada."
            )
        finally:
            # CRITICAL: Always clear the user's busy state
            await session_manager.clear_session(from_number)
            logger.info("User session cleared, busy state released.", extra={"user_id": from_number})

    async def _create_and_process_interview(self, message_data: Dict) -> Interview:
        """Handles the core logic of creating and processing an interview."""
        from_number = message_data["from"]
        message_id = message_data["message_id"]
        media_id = message_data["media_id"]
        
        # Handle different types of media_id
        if isinstance(media_id, dict):
            if media_id.get("source") == "youtube":
                # For YouTube videos, create a unique ID from the metadata
                video_id = media_id.get("metadata", {}).get("video_id", "unknown")
                audio_id = f"youtube_{video_id}_{int(message_data.get('timestamp', 0))}"
            else:
                # For Telegram media (dictionary format), create a unique ID
                chat_id = media_id.get("chat", {}).get("id", "unknown")
                msg_id = media_id.get("message_id", "unknown")
                audio_id = f"telegram_{chat_id}_{msg_id}"
        else:
            # Regular media_id (string) - typically from WhatsApp
            audio_id = media_id

        # Get user's selected prompt
        prompt_manager = PromptManagerService()
        prompt = await prompt_manager.get_user_default_or_popular(from_number, PromptCategory.INTERVIEW_ANALYSIS)
        if not prompt:
            prompt = await prompt_manager.get_default_prompt_for_category(PromptCategory.INTERVIEW_ANALYSIS)
            logger.info("Applied default prompt", extra={"prompt_id": prompt.id if prompt else "None"})

        # Get provider name
        provider_name = self.provider.get_provider_name()

        # Create interview entity
        interview = Interview(
            phone_number=from_number,
            message_id=message_id,
            audio_id=audio_id,
            selected_prompt_id=prompt.id if prompt else None
        )
        await self.interview_repo.create(interview)
        
        # Start processing
        interview.status = InterviewStatus.PROCESSING
        await self.interview_repo.update(interview)
        
        # Run the full processing pipeline
        await self.process_interview_pipeline(interview, media_id, prompt)
        
        return interview

    async def process_interview_pipeline(self, interview: Interview, original_media_id=None, prompt=None):
        """The full pipeline from download to sending documents."""
        progress_tracker = ProgressTracker(self.provider, interview.phone_number)

        # 1. Download and Convert
        await progress_tracker.send_progress_message("🎵 Baixando e convertendo áudio...")
        
        # Check if this is a YouTube video with embedded data
        if interview.audio_id.startswith("youtube_") and isinstance(original_media_id, dict):
            # For YouTube videos, extract the video data from the original media_id
            audio_bytes = original_media_id.get("video_data")
            if not audio_bytes:
                raise Exception("Failed to get YouTube video data")
        elif interview.audio_id.startswith("telegram_") and isinstance(original_media_id, dict):
            # For Telegram media, use the original media_id (dictionary format)
            audio_bytes = await self.provider.download_media(original_media_id)
            if not audio_bytes:
                raise Exception("Failed to download Telegram media")
        else:
            # Regular media download (WhatsApp uses string media_id)
            audio_bytes = await self.provider.download_media(interview.audio_id)
            if not audio_bytes:
                raise Exception("Failed to download audio")
        
        mp3_bytes = self.audio_processor.convert_to_mp3(audio_bytes)
        chunks = self.audio_processor.split_into_chunks(mp3_bytes)
        interview.chunks_total = len(chunks)
        await self.interview_repo.update(interview)

        # 2. Transcribe
        interview.status = InterviewStatus.TRANSCRIBING
        await self.interview_repo.update(interview)
        await progress_tracker.send_progress_message(f"🎙️ Transcrevendo {len(chunks)} parte(s)...")
        
        # Create progress callback for transcription
        async def transcription_progress_callback(interview_obj, chunk_index):
            total_chunks = len(chunks)
            progress_msg = f"🎙️ Transcrevendo parte {chunk_index}/{total_chunks}..."
            await progress_tracker.send_progress_message(progress_msg, force=True)
        
        transcript = await self.transcription_service.transcribe_chunks(chunks, interview, transcription_progress_callback)
        if not transcript:
            raise Exception("Transcription failed")
        interview.transcript = transcript
        await self.interview_repo.update(interview)

        # 3. Analyze
        interview.status = InterviewStatus.ANALYZING
        await self.interview_repo.update(interview)
        await progress_tracker.send_progress_message("🧠 Analisando o conteúdo...")
        
        # Get prompt text from the selected prompt
        prompt_text = prompt.prompt_text if prompt else None
        analysis = await self.analysis_service.generate_report(transcript, prompt_text)
        interview.analysis = analysis
        await self.interview_repo.update(interview)

        # 4. Generate and Send Documents
        await progress_tracker.send_progress_message("📄 Gerando documentos finais...")
        transcript_path, analysis_path = self.doc_generator.create_documents(transcript, analysis, interview.id)
        
        if transcript_path:
            await self.provider.send_document(interview.phone_number, transcript_path, f"📝 Transcrição (ID: {interview.id[:8]})", os.path.basename(transcript_path))
        if analysis_path:
            await self.provider.send_document(interview.phone_number, analysis_path, f"📊 Análise (ID: {interview.id[:8]})", os.path.basename(analysis_path))

        # 5. Mark as complete
        interview.status = InterviewStatus.COMPLETED
        await self.interview_repo.update(interview)
        await progress_tracker.send_progress_message("✅ Processamento concluído!")
        
        # Clean up temp files
        if transcript_path and os.path.exists(transcript_path):
            os.remove(transcript_path)
        if analysis_path and os.path.exists(analysis_path):
            os.remove(analysis_path)
