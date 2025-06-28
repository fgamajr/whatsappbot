from typing import Dict
import logging
import os
from app.domain.entities.interview import Interview, InterviewStatus
from app.infrastructure.database.repositories.interview import InterviewRepository
from app.infrastructure.whatsapp.client import WhatsAppClient
from app.services.audio_processor import AudioProcessor
from app.services.transcription import TranscriptionService
from app.services.analysis import AnalysisService
from app.services.document_generator import DocumentGenerator
from app.core.config import settings

logger = logging.getLogger(__name__)


class MessageHandler:
    def __init__(self):
        self.interview_repo = InterviewRepository()
        self.whatsapp = WhatsAppClient()
        self.audio_processor = AudioProcessor(settings.AUDIO_CHUNK_MINUTES)
        self.transcription = TranscriptionService()
        self.analysis = AnalysisService()
        self.doc_generator = DocumentGenerator()
    
    async def process_audio_message(self, message_data: Dict):
        """Process audio message with full error handling"""
        interview = None
        
        try:
            # Create interview record
            interview = Interview(
                phone_number=message_data["from"],
                message_id=message_data["message_id"],
                audio_id=message_data["media_id"]
            )
            
            await self.interview_repo.create(interview)
            
            # Update status
            interview.mark_processing()
            await self.interview_repo.update(interview)
            
            # Process audio
            await self._process_audio(interview)
            
        except Exception as e:
            logger.error("Audio processing failed", extra={
                "error": str(e),
                "interview_id": interview.id if interview else "unknown"
            })
            
            if interview:
                interview.mark_failed(str(e))
                await self.interview_repo.update(interview)
                
                await self.whatsapp.send_text_message(
                    interview.phone_number,
                    f"❌ Erro no processamento: {str(e)}"
                )
    
    async def _process_audio(self, interview: Interview):
        """Internal audio processing logic"""
        # Step 1: Download audio
        await self.whatsapp.send_text_message(
            interview.phone_number,
            "🎵 Baixando áudio..."
        )
        
        audio_bytes = await self.whatsapp.download_media(interview.audio_id)
        if not audio_bytes:
            raise Exception("Failed to download audio")
        
        interview.audio_size_mb = len(audio_bytes) / (1024 * 1024)
        
        # Step 2: Convert and split
        await self.whatsapp.send_text_message(
            interview.phone_number,
            f"🔄 Convertendo e dividindo áudio ({interview.audio_size_mb:.1f}MB)\n📝 Transcrição com timestamps"
        )
        
        mp3_bytes = self.audio_processor.convert_to_mp3(audio_bytes)
        chunks = self.audio_processor.split_into_chunks(mp3_bytes)
        
        interview.chunks_total = len(chunks)
        await self.interview_repo.update(interview)
        
        # Step 3: Transcribe
        interview.status = InterviewStatus.TRANSCRIBING
        await self.interview_repo.update(interview)
        
        transcript = await self.transcription.transcribe_chunks(
            chunks, interview, self._update_progress
        )
        
        if not transcript:
            raise Exception("Transcription failed")
        
        interview.transcript = transcript
        
        # Step 4: Generate analysis
        interview.status = InterviewStatus.ANALYZING
        await self.interview_repo.update(interview)
        
        await self.whatsapp.send_text_message(
            interview.phone_number,
            "🧠 Gerando análise estruturada..."
        )
        
        analysis = await self.analysis.generate_report(transcript)
        if analysis:
            interview.analysis = analysis
        
        # Step 5: Create and send documents
        await self._create_and_send_documents(interview)
        
        # Mark completed
        interview.mark_completed()
        await self.interview_repo.update(interview)
        
        # Final message
        await self.whatsapp.send_text_message(
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
        
        await self.whatsapp.send_text_message(
            interview.phone_number,
            f"🎙️ Transcrevendo chunk {chunk_num}/{interview.chunks_total}"
        )
    
    async def _create_and_send_documents(self, interview: Interview):
        """Create and send documents"""
        await self.whatsapp.send_text_message(
            interview.phone_number,
            "📄 Criando documentos..."
        )
        
        # Create transcript document
        transcript_path, analysis_path = self.doc_generator.create_documents(
            interview.transcript,
            interview.analysis or "Análise não disponível",
            interview.id
        )
        
        try:
            # Upload and send transcript
            transcript_media_id = await self.whatsapp.upload_media(transcript_path)
            if transcript_media_id:
                await self.whatsapp.send_document(
                    interview.phone_number,
                    transcript_media_id,
                    f"📝 TRANSCRIÇÃO (ID: {interview.id[:8]})",
                    f"transcricao_{interview.id[:8]}.docx"
                )
            
            # Upload and send analysis if available
            if interview.analysis and analysis_path:
                analysis_media_id = await self.whatsapp.upload_media(analysis_path)
                if analysis_media_id:
                    await self.whatsapp.send_document(
                        interview.phone_number,
                        analysis_media_id,
                        f"📊 ANÁLISE (ID: {interview.id[:8]})",
                        f"analise_{interview.id[:8]}.docx"
                    )
            
        finally:
            # Clean up files
            for path in [transcript_path, analysis_path]:
                try:
                    if path and os.path.exists(path):
                        os.remove(path)
                except:
                    pass