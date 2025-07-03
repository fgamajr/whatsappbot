from typing import Dict, Any
import logging
import os
from app.domain.entities.interview import Interview, InterviewStatus
from app.infrastructure.database.repositories.interview import InterviewRepository
from app.infrastructure.messaging.base import MessagingProvider
from app.infrastructure.messaging.factory import MessagingProviderFactory
from app.services.audio_processor import AudioProcessor
from app.services.transcription import TranscriptionService
from app.services.analysis import AnalysisService
from app.services.document_generator import DocumentGenerator
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
    
    # ---> INÍCIO DA MODIFICAÇÃO 3: Assinatura e chamada de download <---
    async def _process_audio(self, interview: Interview, media_payload: Any):
        """Internal audio processing logic"""
        await self.messaging_provider.send_text_message(
            interview.phone_number,
            "🎵 Baixando áudio..."
        )
        
        # 5. Usamos o media_payload (objeto completo) para o download.
        audio_bytes = await self.messaging_provider.download_media(media_payload)
        # ---> FIM DA MODIFICAÇÃO 3 <---

        if not audio_bytes:
            raise Exception("Failed to download audio")
        
        interview.audio_size_mb = len(audio_bytes) / (1024 * 1024)
        
        # ... (O resto do seu código robusto é preservado sem alterações) ...
        await self.messaging_provider.send_text_message(
            interview.phone_number,
            f"🔄 Convertendo e dividindo áudio ({interview.audio_size_mb:.1f}MB)\n📝 Transcrição com timestamps"
        )
        
        mp3_bytes = self.audio_processor.convert_to_mp3(audio_bytes)
        chunks = self.audio_processor.split_into_chunks(mp3_bytes)
        
        interview.chunks_total = len(chunks)
        await self.interview_repo.update(interview)
        
        interview.status = InterviewStatus.TRANSCRIBING
        await self.interview_repo.update(interview)
        
        transcript = await self.transcription.transcribe_chunks(
            chunks, interview, self._update_progress
        )
        
        if not transcript:
            raise Exception("Transcription failed")
        
        interview.transcript = transcript
        
        interview.status = InterviewStatus.ANALYZING
        await self.interview_repo.update(interview)
        
        await self.messaging_provider.send_text_message(
            interview.phone_number,
            "🧠 Gerando análise estruturada..."
        )
        
        analysis = await self.analysis.generate_report(transcript)
        if analysis:
            interview.analysis = analysis
        
        await self._create_and_send_documents(interview)
        
        interview.mark_completed()
        await self.interview_repo.update(interview)
        
        await self.messaging_provider.send_text_message(
            interview.phone_number,
            f"🎉 Processamento completo! (ID: {interview.id[:8]})\n\n"
            f"📝 Transcrição: Com timestamps precisos\n"
            f"📄 {2 if analysis else 1} documento(s) enviado(s)\n"
            f"⏱️ Processamento em background concluído!"
        )
    
    async def _update_progress(self, interview: Interview, chunk_num: int):
        """Update processing progress"""
        interview.chunks_processed = chunk_num
        await self.interview_repo.update(interview)
        
        await self.messaging_provider.send_text_message(
            interview.phone_number,
            f"🎙️ Transcrevendo chunk {chunk_num}/{interview.chunks_total}"
        )
    
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
        """Create and send documents"""
        await self.messaging_provider.send_text_message(
            interview.phone_number,
            "📄 Criando documentos..."
        )
        
        transcript_path, analysis_path = self.doc_generator.create_documents(
            interview.transcript,
            interview.analysis or "Análise não disponível",
            interview.id
        )
        
        try:
            transcript_media_id = await self.messaging_provider.upload_media(transcript_path)
            if transcript_media_id:
                await self.messaging_provider.send_document(
                    interview.phone_number,
                    transcript_media_id,
                    f"📝 TRANSCRIÇÃO (ID: {interview.id[:8]})",
                    f"transcricao_{interview.id[:8]}.docx"
                )
            
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
            for path in [transcript_path, analysis_path]:
                try:
                    if path and os.path.exists(path):
                        os.remove(path)
                except (OSError, IOError, FileNotFoundError) as e:
                    logger.warning(f"Failed to remove file {path}: {e}")