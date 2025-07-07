from typing import Dict, Any
import logging
import os
import asyncio
from app.domain.entities.interview import Interview, InterviewStatus
from app.infrastructure.database.repositories.interview import InterviewRepository
from app.infrastructure.messaging.base import MessagingProvider
from app.infrastructure.messaging.factory import MessagingProviderFactory
from app.services.audio_processor import AudioProcessor
from app.services.transcription import TranscriptionService
from app.services.analysis import AnalysisService
from app.services.document_generator import DocumentGenerator
from app.services.prompt_manager import PromptManagerService
from app.services.user_session_manager import UserSessionManager
from app.utils.progress_tracker import ProgressTracker, TimeEstimator
from app.core.config import settings

logger = logging.getLogger(__name__)


class MessageHandler:
    def __init__(self, messaging_provider: MessagingProvider = None):
        self.interview_repo = InterviewRepository()
        self.messaging_provider = messaging_provider or MessagingProviderFactory.get_default_provider()
        self.audio_processor = AudioProcessor(settings.AUDIO_CHUNK_MINUTES)
        self.transcription = TranscriptionService()
        self.analysis = AnalysisService()
        self.doc_generator = DocumentGenerator()
        self.prompt_manager = PromptManagerService()
        self.session_manager = UserSessionManager()

    # ---> INÍCIO DA MODIFICAÇÃO 1: Função auxiliar <---
    def _get_file_id_from_message(self, message_obj: Dict[str, Any]) -> str:
        """Extrai o file_id de um objeto de mensagem do Telegram de forma segura."""
        for media_type in ['audio', 'voice', 'document', 'video']:
            if media_type in message_obj and 'file_id' in message_obj[media_type]:
                return message_obj[media_type]['file_id']
        # Retorna um ID genérico se não encontrar, para evitar falhas.
        # O download falhará depois, mas a entrevista será criada.
        return f"unknown_file_id_{message_obj.get('message_id', 'N/A')}"
    # ---> FIM DA MODIFICAÇÃO 1 <---

    async def process_audio_message(self, message_data: Dict):
        """Process audio message with full error handling and debugging"""
        interview = None
        
        try:
            print(f"🎵 === PROCESSAMENTO DE ÁUDIO INICIADO ===")
            print(f"🎵 Message data: {message_data}")

            # ---> INÍCIO DA MODIFICAÇÃO 2: Lógica de criação da entrevista <---
            
            # 1. O 'media_id' agora contém o objeto completo da mensagem (payload).
            media_payload = message_data["media_id"]

            # 2. Extraímos o ID do arquivo (string) para salvar no banco.
            audio_id_str = self._get_file_id_from_message(media_payload)
            
            # 3. Criamos a 'Interview' com o ID de áudio correto (string).
            interview = Interview(
                phone_number=message_data["from"],
                message_id=message_data["message_id"],
                audio_id=audio_id_str
            )
            
            # 4. Verificar se o usuário tem uma preferência de prompt recente ou sessão ativa
            try:
                # First check if user has custom instructions waiting
                if await self.session_manager.is_waiting_for_audio(message_data["from"]):
                    session = await self.session_manager.session_repo.get_session(message_data["from"])
                    if session:
                        custom_prompt_id = session.get_context_value("custom_prompt_id")
                        custom_instructions = session.get_context_value("custom_instructions")
                        
                        if custom_prompt_id and custom_instructions:
                            interview.set_selected_prompt(custom_prompt_id)
                            # Store custom instructions in interview context
                            interview.custom_instructions = custom_instructions
                            
                            logger.info("Applied user's custom prompt with instructions", extra={
                                "user_id": message_data["from"],
                                "prompt_id": custom_prompt_id,
                                "instructions_length": len(custom_instructions)
                            })
                            
                            # Clear session after applying
                            await self.session_manager.clear_session(message_data["from"])
                        
                else:
                    # Regular preference check
                    user_pref = await self.prompt_manager.prompt_repo.get_user_preference(message_data["from"])
                    if user_pref and user_pref.last_selected_prompt_id:
                        interview.set_selected_prompt(user_pref.last_selected_prompt_id)
                        logger.info("Applied user's last selected prompt", extra={
                            "user_id": message_data["from"],
                            "prompt_id": user_pref.last_selected_prompt_id
                        })
                        
            except Exception as e:
                logger.warning("Failed to get user prompt preference", extra={
                    "error": str(e),
                    "user_id": message_data["from"]
                })
            
            # ---> FIM DA MODIFICAÇÃO 2 <---
            
            print(f"🎵 Interview criada: {interview.id}")
            
            await self.interview_repo.create(interview)
            print(f"🎵 Interview salva no banco")
            
            interview.mark_processing()
            await self.interview_repo.update(interview)
            print(f"🎵 Status atualizado para PROCESSING")
            
            print(f"🎵 Iniciando processamento de áudio...")
            
            # 4. Passamos o objeto completo (media_payload) para o processamento.
            await self._process_audio(interview, media_payload)
            print(f"🎵 ✅ Processamento concluído com sucesso!")
            
        except Exception as e:
            # Sua excelente lógica de tratamento de erros é preservada.
            print(f"🚨 === ERRO NO PROCESSAMENTO DE ÁUDIO ===")
            print(f"🚨 Erro: {e}")
            print(f"🚨 Tipo: {type(e).__name__}")
            print(f"🚨 Interview ID: {interview.id if interview else 'N/A'}")
            print(f"🚨 Message data: {message_data}")
            print(f"🚨 Traceback completo:")
            import traceback
            traceback.print_exc()
            print(f"🚨 ========================================")
            
            logger.error("Audio processing failed", extra={
                "error": str(e),
                "interview_id": interview.id if interview else "unknown"
            })
            
            if interview:
                interview.mark_failed(str(e))
                await self.interview_repo.update(interview)
                
                print(f"🚨 Enviando mensagem de erro para usuário...")
                await self.messaging_provider.send_text_message(
                    interview.phone_number,
                    f"❌ Erro no processamento: {str(e)}"
                )
                print(f"🚨 Mensagem de erro enviada")
    
    async def _process_audio(self, interview: Interview, media_payload: Any):
        """Internal audio processing logic with progress tracking"""
        # Create progress tracker
        progress_tracker = ProgressTracker(self.messaging_provider, interview.phone_number)
        
        # Download audio
        await progress_tracker.send_progress_message("🎵 Baixando áudio...", force=True)
        audio_bytes = await self.messaging_provider.download_media(media_payload)
        
        if not audio_bytes:
            raise Exception("Failed to download audio")
        
        interview.audio_size_mb = len(audio_bytes) / (1024 * 1024)
        
        # Estimate audio duration (rough estimate: 1MB ≈ 1 minute for typical voice)
        estimated_duration = interview.audio_size_mb * 1.2  # conservative estimate
        
        # Get time estimates
        time_estimates = TimeEstimator.estimate_total_processing_time(
            interview.audio_size_mb, 
            estimated_duration
        )
        
        # Send concise initial estimate to user
        if time_estimates['total_minutes'] > 3:
            estimate_msg = (
                f"📊 Áudio: {interview.audio_size_mb:.1f}MB\n"
                f"⏱️ Estimado: ~{time_estimates['total_minutes']:.1f}min\n"
                f"🔄 {time_estimates['num_chunks']} chunks para processar"
            )
            await progress_tracker.send_progress_message(estimate_msg, force=True)
        
        # Audio conversion (no heartbeat for fast operations)
        await progress_tracker.send_progress_message("🔄 Convertendo áudio...", force=True)
        mp3_bytes = self.audio_processor.convert_to_mp3(audio_bytes)
        
        # Split into chunks
        chunks = self.audio_processor.split_into_chunks(mp3_bytes)
        interview.chunks_total = len(chunks)
        await self.interview_repo.update(interview)
        
        # Update status
        interview.status = InterviewStatus.TRANSCRIBING
        await self.interview_repo.update(interview)
        
        # Simple transcription start message
        if len(chunks) > 1:
            await progress_tracker.send_progress_message(
                f"🎙️ Iniciando transcrição ({len(chunks)} chunks)",
                force=True
            )
        
        transcript = await self.transcription.transcribe_chunks(
            chunks, interview, self._update_progress_enhanced
        )
        
        if not transcript:
            raise Exception("Transcription failed")
        
        interview.transcript = transcript
        
        # Analysis with minimal tracking
        interview.status = InterviewStatus.ANALYZING
        await self.interview_repo.update(interview)
        
        # Only use heartbeat for longer analysis
        if time_estimates['analysis_minutes'] > 2:
            async def generate_analysis():
                return await self.analysis.generate_report(
                    transcript, 
                    user_id=interview.phone_number,
                    prompt_identifier=interview.selected_prompt_id,
                    custom_instructions=getattr(interview, 'custom_instructions', None)
                )
            
            analysis = await progress_tracker.run_with_heartbeat(
                generate_analysis,
                "Gerando análise com IA",
                time_estimates['analysis_minutes']
            )
        else:
            await progress_tracker.send_progress_message("🧠 Gerando análise...", force=True)
            analysis = await self.analysis.generate_report(
                transcript, 
                user_id=interview.phone_number,
                prompt_identifier=interview.selected_prompt_id,
                custom_instructions=getattr(interview, 'custom_instructions', None)
            )
        
        if analysis:
            interview.analysis = analysis
        
        # Document generation (no heartbeat for fast operation)
        await self._create_and_send_documents(interview)
        
        # Final completion
        interview.mark_completed()
        await self.interview_repo.update(interview)
        
        await progress_tracker.send_progress_message(
            f"🎉 Processamento completo!\n"
            f"📄 {2 if analysis else 1} documento(s) enviado(s)",
            force=True
        )
    
    async def _update_progress_enhanced(self, interview: Interview, chunk_num: int):
        """Enhanced progress update with time estimates"""
        interview.chunks_processed = chunk_num
        await self.interview_repo.update(interview)
        
        # Only send progress for the START of each chunk, not completion
        # This prevents the 100% issue
        if chunk_num <= interview.chunks_total:
            # Calculate progress for chunks STARTED (not completed)
            progress_percent = ((chunk_num - 1) / interview.chunks_total) * 100
            remaining_chunks = interview.chunks_total - chunk_num + 1
            
            # Simple message - no spam
            progress_msg = f"🎙️ Processando chunk {chunk_num}/{interview.chunks_total}"
            
            # Only add timing for longer processes
            if interview.chunks_total > 2 and remaining_chunks > 0:
                estimated_remaining_minutes = remaining_chunks * 2.5
                if estimated_remaining_minutes > 1:
                    progress_msg += f" (~{estimated_remaining_minutes:.1f}min restantes)"
            
            await self.messaging_provider.send_text_message(
                interview.phone_number,
                progress_msg
            )
    
    async def _update_progress(self, interview: Interview, chunk_num: int):
        """Legacy progress update method for compatibility"""
        await self._update_progress_enhanced(interview, chunk_num)
    
    async def _handle_large_audio_error(self, interview: Interview, error_message: str):
        """Handle large audio files with helpful guidance"""
        size_info = ""
        if "MB" in error_message:
            size_info = f"\n\n📊 {error_message.split('Áudio convertido:')[1].split('💡')[0].strip()}" if "Áudio convertido:" in error_message else ""
        
        helpful_message = f"""
🚫 **Áudio muito grande para processamento**

{error_message}

🎯 **Por que isso acontece?**
• Validação é feita APÓS conversão inteligente
• Arquivos grandes → áudios menores, mas ainda grandes
• Limite técnico da API de transcrição

🎤 **Melhores práticas:**
• **Gravar direto:** Use gravação nativa do app
• **Tempo menor:** Máximo 30-45 minutos por áudio  
• **Qualidade média:** Não precisa ser alta qualidade
• **Dividir:** Corte em partes de 20-30 minutos

🔄 **Tente novamente:**
• Arquivo menor ou dividido
• Gravação nativa do Telegram/WhatsApp
• Compressão prévia se necessário

⚡ **Resposta rápida + processamento em background sempre!**
        """
        
        await self.messaging_provider.send_text_message(
            interview.phone_number,
            helpful_message
        )
        
        interview.mark_failed(f"Audio too large after conversion: {error_message}")
        await self.interview_repo.update(interview)

    async def _create_and_send_documents(self, interview: Interview):
        """Create and send documents with minimal progress updates"""
        await self.messaging_provider.send_text_message(
            interview.phone_number,
            "📄 Criando documentos..."
        )
        
        # Generate documents
        transcript_path, analysis_path = self.doc_generator.create_documents(
            interview.transcript,
            interview.analysis or "Análise não disponível",
            interview.id
        )
        
        try:
            # Upload and send transcript (no separate message)
            transcript_media_id = await self.messaging_provider.upload_media(transcript_path)
            if transcript_media_id:
                await self.messaging_provider.send_document(
                    interview.phone_number,
                    transcript_media_id,
                    f"📝 TRANSCRIÇÃO (ID: {interview.id[:8]})",
                    f"transcricao_{interview.id[:8]}.docx"
                )
            
            # Upload and send analysis if available (no separate message)
            if interview.analysis and analysis_path:
                analysis_media_id = await self.messaging_provider.upload_media(analysis_path)
                if analysis_media_id:
                    await self.messaging_provider.send_document(
                        interview.phone_number,
                        analysis_media_id,
                        f"📊 ANÁLISE (ID: {interview.id[:8]})",
                        f"analise_{interview.id[:8]}.docx"
                    )
        finally:
            # Clean up temporary files
            for path in [transcript_path, analysis_path]:
                try:
                    if path and os.path.exists(path):
                        os.remove(path)
                except:
                    pass