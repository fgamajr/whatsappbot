from typing import Optional, List, Tuple, Callable
import logging
import time
from app.infrastructure.ai.whisper import WhisperService
from app.domain.entities.interview import Interview
from app.core.exceptions import TranscriptionError
from app.utils.progress_tracker import TimeEstimator

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
        """Transcribe audio chunks with enhanced progress tracking"""
        try:
            full_transcript = ""
            total_chunks = len(chunks)
            
            logger.info("Starting chunk transcription", extra={
                "total_chunks": total_chunks,
                "interview_id": interview.id
            })
            
            for i, (chunk_bytes, start_time_minutes, duration_minutes) in enumerate(chunks):
                chunk_index = i + 1
                chunk_size_mb = len(chunk_bytes) / (1024 * 1024)
                
                logger.info("Transcribing chunk", extra={
                    "chunk_index": chunk_index,
                    "total_chunks": total_chunks,
                    "start_time_minutes": start_time_minutes,
                    "duration_minutes": duration_minutes,
                    "chunk_size_mb": chunk_size_mb
                })
                
                # Progress callback with timing info
                if progress_callback:
                    await progress_callback(interview, chunk_index)
                
                # Record start time for this chunk
                chunk_start_time = time.time()
                
                # Transcribe with progress tracking
                chunk_transcript = await self._transcribe_simple(chunk_bytes)
                
                # Log chunk completion time
                chunk_duration = time.time() - chunk_start_time
                logger.info("Chunk transcription completed", extra={
                    "chunk_index": chunk_index,
                    "processing_time_seconds": chunk_duration,
                    "success": chunk_transcript is not None
                })
                
                if not chunk_transcript:
                    logger.warning("Chunk transcription failed", extra={
                        "chunk_index": chunk_index,
                        "chunk_size_mb": chunk_size_mb
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
                
                # Log progress
                progress_percent = (chunk_index / total_chunks) * 100
                logger.info("Transcription progress update", extra={
                    "chunks_completed": chunk_index,
                    "total_chunks": total_chunks,
                    "progress_percent": progress_percent
                })
            
            if full_transcript:
                logger.info("Transcription completed successfully", extra={
                    "total_chunks": total_chunks,
                    "transcript_length": len(full_transcript),
                    "interview_id": interview.id
                })
            
            return full_transcript if full_transcript else None
            
        except Exception as e:
            logger.error("Chunk transcription process failed", extra={
                "error": str(e),
                "interview_id": interview.id,
                "total_chunks": len(chunks)
            })
            raise TranscriptionError(f"Failed to transcribe chunks: {str(e)}")
    
    async def _transcribe_simple(self, audio_bytes: bytes) -> Optional[str]:
        """Transcrição com timestamps apenas - sem identificação de locutores"""
        try:
            chunk_size_mb = len(audio_bytes) / (1024 * 1024)
            
            logger.info("Starting Whisper transcription", extra={
                "chunk_size_mb": chunk_size_mb
            })
            
            # Record API call timing
            api_start_time = time.time()
            result = await self.whisper.transcribe(audio_bytes)
            api_duration = time.time() - api_start_time
            
            logger.info("Whisper API call completed", extra={
                "api_duration_seconds": api_duration,
                "chunk_size_mb": chunk_size_mb,
                "success": result is not None
            })
            
            if not result or not result.get("text"):
                logger.warning("Whisper returned empty result", extra={
                    "chunk_size_mb": chunk_size_mb
                })
                return None
            
            # Convert to simple timestamped format
            transcript_lines = []
            segments = result.get("segments", [])
            
            logger.info("Processing Whisper segments", extra={
                "segments_count": len(segments),
                "full_text_length": len(result.get("text", ""))
            })
            
            for segment in segments:
                start_min = int(segment["start"] // 60)
                start_sec = int(segment["start"] % 60)
                end_min = int(segment["end"] // 60)
                end_sec = int(segment["end"] % 60)
                
                timestamp = f"[{start_min:02d}:{start_sec:02d}-{end_min:02d}:{end_sec:02d}]"
                text = segment["text"].strip()
                
                transcript_lines.append(f"{timestamp} {text}")
            
            final_transcript = "\n".join(transcript_lines)
            
            logger.info("Transcription formatting completed", extra={
                "final_length": len(final_transcript),
                "lines_count": len(transcript_lines)
            })
            
            return final_transcript
            
        except Exception as e:
            logger.error("Simple transcription failed", extra={
                "error": str(e),
                "chunk_size_mb": len(audio_bytes) / (1024 * 1024)
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