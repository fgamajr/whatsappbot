from typing import Optional, List, Tuple, Callable
import logging
from app.infrastructure.ai.whisper import WhisperService
from app.domain.entities.interview import Interview
from app.core.exceptions import TranscriptionError

logger = logging.getLogger(__name__)


class TranscriptionService:
    def __init__(self):
        self.whisper = WhisperService()
    
    async def transcribe_chunks(
        self,
        chunks: List[Tuple[bytes, float, float]],
        interview: Interview,
        progress_callback: Optional[Callable] = None
    ) -> Optional[str]:
        """Transcribe audio chunks with progress tracking"""
        try:
            full_transcript = ""
            
            for i, (chunk_bytes, start_time_minutes, duration_minutes) in enumerate(chunks):
                logger.info("Transcribing chunk", extra={
                    "chunk_index": i + 1,
                    "total_chunks": len(chunks),
                    "start_time_minutes": start_time_minutes,
                    "duration_minutes": duration_minutes
                })
                
                # Progress callback
                if progress_callback:
                    await progress_callback(interview, i + 1)
                
                # Sempre usar transcrição simples (sem locutores fake)
                chunk_transcript = await self._transcribe_simple(chunk_bytes)
                
                if not chunk_transcript:
                    logger.warning("Chunk transcription failed", extra={
                        "chunk_index": i + 1
                    })
                    continue
                
                # Adjust timestamps if not first chunk
                if start_time_minutes > 0:
                    chunk_transcript = self._adjust_timestamps(
                        chunk_transcript, 
                        start_time_minutes
                    )
                
                # Combine transcripts
                if full_transcript:
                    full_transcript += "\n\n" + chunk_transcript
                else:
                    full_transcript = chunk_transcript
            
            return full_transcript if full_transcript else None
            
        except Exception as e:
            logger.error("Chunk transcription process failed", extra={
                "error": str(e),
                "interview_id": interview.id
            })
            raise TranscriptionError(f"Failed to transcribe chunks: {str(e)}")
    
    async def _transcribe_simple(self, audio_bytes: bytes) -> Optional[str]:
        """Transcrição com timestamps apenas - sem identificação de locutores"""
        try:
            result = await self.whisper.transcribe(audio_bytes)
            
            if not result or not result.get("text"):
                return None
            
            # Convert to simple timestamped format
            transcript_lines = []
            
            for segment in result.get("segments", []):
                start_min = int(segment["start"] // 60)
                start_sec = int(segment["start"] % 60)
                end_min = int(segment["end"] // 60)
                end_sec = int(segment["end"] % 60)
                
                timestamp = f"[{start_min:02d}:{start_sec:02d}-{end_min:02d}:{end_sec:02d}]"
                text = segment["text"].strip()
                
                transcript_lines.append(f"{timestamp} {text}")
            
            return "\n".join(transcript_lines)
            
        except Exception as e:
            logger.error("Simple transcription failed", extra={
                "error": str(e)
            })
            return None
    
    def _adjust_timestamps(self, transcript: str, offset_minutes: float) -> str:
        """Adjust timestamps by adding offset"""
        import re
        
        def adjust_match(match):
            start_min = int(match.group(1)) + int(offset_minutes)
            start_sec = int(match.group(2))
            
            if match.group(3) and match.group(4):  # Range format
                end_min = int(match.group(3)) + int(offset_minutes)
                end_sec = int(match.group(4))
                return f"[{start_min:02d}:{start_sec:02d}-{end_min:02d}:{end_sec:02d}]"
            else:  # Single timestamp
                return f"[{start_min:02d}:{start_sec:02d}]"
        
        pattern = r'\[(\d{1,2}):(\d{2})(?:-(\d{1,2}):(\d{2}))?\]'
        return re.sub(pattern, adjust_match, transcript)