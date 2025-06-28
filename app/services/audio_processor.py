from typing import List, Tuple
import io
import logging
from pydub import AudioSegment
from app.core.exceptions import AudioProcessingError

logger = logging.getLogger(__name__)


class AudioProcessor:
    def __init__(self, chunk_duration_minutes: int = 15):
        self.chunk_duration_minutes = chunk_duration_minutes
    
    def convert_to_mp3(self, audio_bytes: bytes) -> bytes:
        """Convert any audio format to MP3"""
        try:
            audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
            
            mp3_buffer = io.BytesIO()
            audio.export(mp3_buffer, format="mp3")
            mp3_bytes = mp3_buffer.getvalue()
            
            logger.info("Audio converted to MP3", extra={
                "original_size": len(audio_bytes),
                "mp3_size": len(mp3_bytes)
            })
            
            return mp3_bytes
            
        except Exception as e:
            logger.error("Audio conversion failed", extra={
                "error": str(e)
            })
            raise AudioProcessingError(f"Failed to convert audio: {str(e)}")
    
    def split_into_chunks(self, audio_bytes: bytes) -> List[Tuple[bytes, float, float]]:
        """Split audio into chunks. Returns (chunk_bytes, start_minutes, duration_minutes)"""
        try:
            audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
            
            chunk_duration_ms = self.chunk_duration_minutes * 60 * 1000
            total_duration_ms = len(audio)
            
            chunks = []
            start_time_ms = 0
            
            logger.info("Splitting audio", extra={
                "total_duration_minutes": total_duration_ms / 1000 / 60,
                "chunk_duration_minutes": self.chunk_duration_minutes
            })
            
            while start_time_ms < total_duration_ms:
                end_time_ms = min(start_time_ms + chunk_duration_ms, total_duration_ms)
                
                chunk = audio[start_time_ms:end_time_ms]
                
                chunk_buffer = io.BytesIO()
                chunk.export(chunk_buffer, format="mp3", parameters=["-q:a", "5"])
                chunk_bytes = chunk_buffer.getvalue()
                
                start_time_minutes = start_time_ms / 1000 / 60
                actual_duration_minutes = (end_time_ms - start_time_ms) / 1000 / 60
                
                chunks.append((chunk_bytes, start_time_minutes, actual_duration_minutes))
                
                logger.info("Chunk created", extra={
                    "chunk_index": len(chunks),
                    "start_minutes": start_time_minutes,
                    "duration_minutes": actual_duration_minutes,
                    "size_bytes": len(chunk_bytes)
                })
                
                start_time_ms = end_time_ms
            
            return chunks
            
        except Exception as e:
            logger.error("Audio splitting failed", extra={
                "error": str(e)
            })
            raise AudioProcessingError(f"Failed to split audio: {str(e)}")
