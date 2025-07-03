from celery import shared_task, group, chain
from typing import Dict, Any, List, Tuple
import logging
import asyncio
from app.domain.entities.interview import Interview, InterviewStatus
from app.infrastructure.database.repositories.interview import InterviewRepository
from app.infrastructure.messaging.factory import MessagingProviderFactory
from app.services.audio_processor import AudioProcessor
from app.services.transcription import TranscriptionService
from app.services.analysis import AnalysisService
from app.services.document_generator import DocumentGenerator
from app.core.config import settings
from app.utils.secure_logging import SecureLogger

logger = logging.getLogger(__name__)

# ================================
# STEP 1: DOWNLOAD & VALIDATE AUDIO
# ================================

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    retry_backoff=True,
    retry_jitter=True,
    name='audio_pipeline.download_audio'
)
def download_audio_task(self, message_data: Dict[str, Any]):
    """
    Step 1: Download audio and create interview record
    
    Returns: interview_data dict with audio_bytes
    """
    try:
        SecureLogger.safe_log_info(logger, "Starting audio download", {
            'task_id': self.request.id,
            'message_id': message_data.get('message_id'),
            'from_user': SecureLogger.mask_phone_number(message_data.get('from', ''))
        })
        
        # Setup async environment
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Create interview record
            from app.services.message_handler import MessageHandler
            handler = MessageHandler()
            
            # Extract audio ID
            media_payload = message_data["media_id"]
            audio_id_str = handler._get_file_id_from_message(media_payload)
            
            # Create interview
            interview = Interview(
                phone_number=message_data["from"],
                message_id=message_data["message_id"],
                audio_id=audio_id_str
            )
            
            # Save to database
            interview_repo = InterviewRepository()
            loop.run_until_complete(interview_repo.create(interview))
            
            # Mark as processing
            interview.mark_processing()
            loop.run_until_complete(interview_repo.update(interview))
            
            # Send initial message
            messaging_provider = MessagingProviderFactory.get_default_provider()
            loop.run_until_complete(messaging_provider.send_text_message(
                interview.phone_number,
                "🎵 Baixando áudio..."
            ))
            
            # Download audio
            audio_bytes = loop.run_until_complete(
                messaging_provider.download_media(media_payload)
            )
            
            if not audio_bytes:
                raise Exception("Failed to download audio")
            
            # Calculate size and update interview
            interview.audio_size_mb = len(audio_bytes) / (1024 * 1024)
            loop.run_until_complete(interview_repo.update(interview))
            
            SecureLogger.safe_log_info(logger, "Audio download completed", {
                'task_id': self.request.id,
                'interview_id': interview.id,
                'audio_size_mb': interview.audio_size_mb
            })
            
            return {
                'interview_id': interview.id,
                'phone_number': interview.phone_number,
                'audio_bytes': audio_bytes.hex(),  # Convert to hex for serialization
                'audio_size_mb': interview.audio_size_mb,
                'message_id': interview.message_id
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Audio download failed", e, {
            'task_id': self.request.id,
            'message_id': message_data.get('message_id')
        })
        raise

# ================================
# STEP 2: CONVERT & CHUNK AUDIO
# ================================

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 30},
    name='audio_pipeline.convert_and_chunk_audio'
)
def convert_and_chunk_audio_task(self, interview_data: Dict[str, Any]):
    """
    Step 2: Convert audio to MP3 and split into chunks
    
    Returns: interview_data with chunks
    """
    try:
        SecureLogger.safe_log_info(logger, "Starting audio conversion and chunking", {
            'task_id': self.request.id,
            'interview_id': interview_data['interview_id'],
            'audio_size_mb': interview_data['audio_size_mb']
        })
        
        # Setup async environment for database operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Convert hex back to bytes
            audio_bytes = bytes.fromhex(interview_data['audio_bytes'])
            
            # Send progress message
            messaging_provider = MessagingProviderFactory.get_default_provider()
            loop.run_until_complete(messaging_provider.send_text_message(
                interview_data['phone_number'],
                f"🔄 Convertendo e dividindo áudio ({interview_data['audio_size_mb']:.1f}MB)\n📝 Preparando para transcrição com timestamps"
            ))
            
            # Convert to MP3
            audio_processor = AudioProcessor(settings.AUDIO_CHUNK_MINUTES)
            mp3_bytes = audio_processor.convert_to_mp3(audio_bytes)
            
            # Split into chunks
            chunks = audio_processor.split_into_chunks(mp3_bytes)
            
            # Update interview with chunk info
            interview_repo = InterviewRepository()
            interview = loop.run_until_complete(
                interview_repo.get_by_id(interview_data['interview_id'])
            )
            
            if not interview:
                raise Exception(f"Interview {interview_data['interview_id']} not found")
            
            interview.chunks_total = len(chunks)
            interview.status = InterviewStatus.TRANSCRIBING
            loop.run_until_complete(interview_repo.update(interview))
            
            # Convert chunks to hex for serialization
            chunks_hex = [chunk.hex() for chunk in chunks]
            
            SecureLogger.safe_log_info(logger, "Audio conversion and chunking completed", {
                'task_id': self.request.id,
                'interview_id': interview_data['interview_id'],
                'chunks_count': len(chunks),
                'mp3_size_mb': len(mp3_bytes) / (1024 * 1024)
            })
            
            # Return data for next step
            interview_data.update({
                'chunks_hex': chunks_hex,
                'chunks_total': len(chunks),
                'mp3_bytes': mp3_bytes.hex()
            })
            
            # Remove original audio_bytes to save memory
            del interview_data['audio_bytes']
            
            return interview_data
            
        finally:
            loop.close()
            
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Audio conversion failed", e, {
            'task_id': self.request.id,
            'interview_id': interview_data.get('interview_id')
        })
        raise

# ================================
# STEP 3: TRANSCRIBE CHUNKS (PARALLEL)
# ================================

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 120},
    retry_backoff=True,
    name='audio_pipeline.transcribe_chunk'
)
def transcribe_chunk_task(self, chunk_data: Dict[str, Any]):
    """
    Step 3a: Transcribe a single audio chunk
    
    Args:
        chunk_data: {
            'chunk_hex': hex string of audio chunk,
            'chunk_index': int,
            'interview_id': str,
            'phone_number': str
        }
    
    Returns: chunk transcript result
    """
    try:
        SecureLogger.safe_log_info(logger, "Starting chunk transcription", {
            'task_id': self.request.id,
            'interview_id': chunk_data['interview_id'],
            'chunk_index': chunk_data['chunk_index']
        })
        
        # Setup async environment
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Convert hex back to bytes
            chunk_bytes = bytes.fromhex(chunk_data['chunk_hex'])
            
            # Send progress update
            messaging_provider = MessagingProviderFactory.get_default_provider()
            loop.run_until_complete(messaging_provider.send_text_message(
                chunk_data['phone_number'],
                f"🎙️ Transcrevendo parte {chunk_data['chunk_index'] + 1}/{chunk_data['total_chunks']}"
            ))
            
            # Update database progress
            interview_repo = InterviewRepository()
            interview = loop.run_until_complete(
                interview_repo.get_by_id(chunk_data['interview_id'])
            )
            
            if interview:
                interview.chunks_processed = chunk_data['chunk_index'] + 1
                loop.run_until_complete(interview_repo.update(interview))
            
            # Transcribe chunk
            transcription_service = TranscriptionService()
            
            # Calculate time offset for this chunk
            chunk_duration_minutes = settings.AUDIO_CHUNK_MINUTES
            time_offset_minutes = chunk_data['chunk_index'] * chunk_duration_minutes
            
            chunk_transcript = loop.run_until_complete(
                transcription_service.transcribe_chunk(
                    chunk_bytes, 
                    time_offset_minutes
                )
            )
            
            if not chunk_transcript:
                raise Exception(f"Transcription failed for chunk {chunk_data['chunk_index']}")
            
            SecureLogger.safe_log_info(logger, "Chunk transcription completed", {
                'task_id': self.request.id,
                'interview_id': chunk_data['interview_id'],
                'chunk_index': chunk_data['chunk_index'],
                'transcript_length': len(chunk_transcript)
            })
            
            return {
                'chunk_index': chunk_data['chunk_index'],
                'transcript': chunk_transcript,
                'interview_id': chunk_data['interview_id']
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Chunk transcription failed", e, {
            'task_id': self.request.id,
            'interview_id': chunk_data.get('interview_id'),
            'chunk_index': chunk_data.get('chunk_index')
        })
        raise

@shared_task(
    bind=True,
    name='audio_pipeline.combine_transcripts'
)
def combine_transcripts_task(self, transcript_results: List[Dict[str, Any]], interview_data: Dict[str, Any]):
    """
    Step 3b: Combine all chunk transcripts into final transcript
    
    Args:
        transcript_results: List of transcript results from parallel tasks
        interview_data: Interview data from previous steps
    
    Returns: interview_data with combined transcript
    """
    try:
        SecureLogger.safe_log_info(logger, "Combining transcripts", {
            'task_id': self.request.id,
            'interview_id': interview_data['interview_id'],
            'transcript_count': len(transcript_results)
        })
        
        # Setup async environment
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Sort transcript results by chunk index
            transcript_results.sort(key=lambda x: x['chunk_index'])
            
            # Combine transcripts
            combined_transcript = ""
            for result in transcript_results:
                if result['transcript']:
                    combined_transcript += result['transcript'] + "\n\n"
            
            combined_transcript = combined_transcript.strip()
            
            if not combined_transcript:
                raise Exception("No transcript content generated")
            
            # Update interview in database
            interview_repo = InterviewRepository()
            interview = loop.run_until_complete(
                interview_repo.get_by_id(interview_data['interview_id'])
            )
            
            if not interview:
                raise Exception(f"Interview {interview_data['interview_id']} not found")
            
            interview.transcript = combined_transcript
            interview.status = InterviewStatus.ANALYZING
            loop.run_until_complete(interview_repo.update(interview))
            
            # Send progress message
            messaging_provider = MessagingProviderFactory.get_default_provider()
            loop.run_until_complete(messaging_provider.send_text_message(
                interview_data['phone_number'],
                "✅ Transcrição concluída!\n🧠 Gerando análise estruturada..."
            ))
            
            SecureLogger.safe_log_info(logger, "Transcripts combined successfully", {
                'task_id': self.request.id,
                'interview_id': interview_data['interview_id'],
                'final_transcript_length': len(combined_transcript)
            })
            
            # Update interview data
            interview_data.update({
                'transcript': combined_transcript,
                'status': 'analyzing'
            })
            
            return interview_data
            
        finally:
            loop.close()
            
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Transcript combination failed", e, {
            'task_id': self.request.id,
            'interview_id': interview_data.get('interview_id')
        })
        raise

# ================================
# STEP 4: GENERATE ANALYSIS
# ================================

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    retry_backoff=True,
    name='audio_pipeline.generate_analysis'
)
def generate_analysis_task(self, interview_data: Dict[str, Any]):
    """
    Step 4: Generate AI analysis of the transcript
    
    Returns: interview_data with analysis
    """
    try:
        SecureLogger.safe_log_info(logger, "Starting analysis generation", {
            'task_id': self.request.id,
            'interview_id': interview_data['interview_id'],
            'transcript_length': len(interview_data.get('transcript', ''))
        })
        
        # Setup async environment
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Generate analysis
            analysis_service = AnalysisService()
            analysis = loop.run_until_complete(
                analysis_service.generate_report(interview_data['transcript'])
            )
            
            # Update interview in database
            interview_repo = InterviewRepository()
            interview = loop.run_until_complete(
                interview_repo.get_by_id(interview_data['interview_id'])
            )
            
            if not interview:
                raise Exception(f"Interview {interview_data['interview_id']} not found")
            
            if analysis:
                interview.analysis = analysis
            
            loop.run_until_complete(interview_repo.update(interview))
            
            SecureLogger.safe_log_info(logger, "Analysis generation completed", {
                'task_id': self.request.id,
                'interview_id': interview_data['interview_id'],
                'analysis_generated': analysis is not None
            })
            
            # Update interview data
            interview_data.update({
                'analysis': analysis,
                'status': 'generating_documents'
            })
            
            return interview_data
            
        finally:
            loop.close()
            
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Analysis generation failed", e, {
            'task_id': self.request.id,
            'interview_id': interview_data.get('interview_id')
        })
        
        # Continue without analysis if it fails
        interview_data.update({
            'analysis': None,
            'status': 'generating_documents'
        })
        
        return interview_data

# ================================
# STEP 5: GENERATE & SEND DOCUMENTS
# ================================

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 30},
    name='audio_pipeline.generate_and_send_documents'
)
def generate_and_send_documents_task(self, interview_data: Dict[str, Any]):
    """
    Step 5: Generate documents and send to user
    
    Returns: final result
    """
    try:
        SecureLogger.safe_log_info(logger, "Starting document generation", {
            'task_id': self.request.id,
            'interview_id': interview_data['interview_id'],
            'has_analysis': interview_data.get('analysis') is not None
        })
        
        # Setup async environment
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Get interview from database
            interview_repo = InterviewRepository()
            interview = loop.run_until_complete(
                interview_repo.get_by_id(interview_data['interview_id'])
            )
            
            if not interview:
                raise Exception(f"Interview {interview_data['interview_id']} not found")
            
            # Generate and send documents
            from app.services.message_handler import MessageHandler
            handler = MessageHandler()
            
            # This uses the existing robust document generation logic
            loop.run_until_complete(handler._create_and_send_documents(interview))
            
            # Mark as completed
            interview.mark_completed()
            loop.run_until_complete(interview_repo.update(interview))
            
            # Send final message
            messaging_provider = MessagingProviderFactory.get_default_provider()
            doc_count = 2 if interview.analysis else 1
            
            loop.run_until_complete(messaging_provider.send_text_message(
                interview.phone_number,
                f"🎉 Processamento completo! (ID: {interview.id[:8]})\n\n"
                f"📝 Transcrição: Com timestamps precisos\n"
                f"📄 {doc_count} documento(s) enviado(s)\n"
                f"⚡ Processamento paralelo concluído!"
            ))
            
            SecureLogger.safe_log_info(logger, "Document generation and sending completed", {
                'task_id': self.request.id,
                'interview_id': interview_data['interview_id'],
                'documents_sent': doc_count
            })
            
            return {
                'status': 'completed',
                'interview_id': interview_data['interview_id'],
                'documents_sent': doc_count,
                'task_id': self.request.id
            }
            
        finally:
            loop.close()
            
    except Exception as e:
        SecureLogger.safe_log_error(logger, "Document generation failed", e, {
            'task_id': self.request.id,
            'interview_id': interview_data.get('interview_id')
        })
        
        # Mark interview as failed
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            interview_repo = InterviewRepository()
            interview = loop.run_until_complete(
                interview_repo.get_by_id(interview_data['interview_id'])
            )
            
            if interview:
                interview.mark_failed(str(e))
                loop.run_until_complete(interview_repo.update(interview))
                
                messaging_provider = MessagingProviderFactory.get_default_provider()
                loop.run_until_complete(messaging_provider.send_text_message(
                    interview.phone_number,
                    f"❌ Erro no processamento final: {str(e)}"
                ))
        finally:
            loop.close()
        
        raise