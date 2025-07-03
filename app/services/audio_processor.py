from typing import List, Tuple
import io
import logging
from pydub import AudioSegment
from app.core.exceptions import AudioProcessingError

logger = logging.getLogger(__name__)


class AudioProcessor:
    def __init__(self, chunk_duration_minutes: int = 15):
        self.chunk_duration_minutes = chunk_duration_minutes
        # Limites inteligentes após conversão
        self.max_converted_size_mb = 25  # Whisper API limit
        self.max_memory_size_mb = 100    # Limite de memória razoável
    
    def convert_to_mp3(self, audio_bytes: bytes) -> bytes:
        """Convert any audio format to MP3 with intelligent validation"""
        try:
            original_size_mb = len(audio_bytes) / (1024 * 1024)
            
            logger.info("Starting audio conversion", extra={
                "original_size_bytes": len(audio_bytes),
                "original_size_mb": round(original_size_mb, 1)
            })
            
            # Carregar áudio (suporta qualquer formato)
            audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
            
            # Conversão inteligente baseada no tamanho original
            if original_size_mb > 50:
                # Arquivo muito grande - compressão agressiva
                export_params = ["-q:a", "9", "-ar", "22050"]  # Qualidade mais baixa
                logger.info("Using aggressive compression for large file")
            elif original_size_mb > 20:
                # Arquivo médio - compressão moderada
                export_params = ["-q:a", "7", "-ar", "44100"]  # Qualidade média
                logger.info("Using moderate compression")
            else:
                # Arquivo pequeno - compressão leve
                export_params = ["-q:a", "5", "-ar", "44100"]  # Qualidade boa
                logger.info("Using light compression")
            
            mp3_buffer = io.BytesIO()
            audio.export(mp3_buffer, format="mp3", parameters=export_params)
            mp3_bytes = mp3_buffer.getvalue()
            
            converted_size_mb = len(mp3_bytes) / (1024 * 1024)
            compression_ratio = original_size_mb / converted_size_mb if converted_size_mb > 0 else 1
            
            logger.info("Audio conversion completed", extra={
                "original_size_mb": round(original_size_mb, 1),
                "converted_size_mb": round(converted_size_mb, 1),
                "compression_ratio": round(compression_ratio, 1),
                "size_reduction_percent": round((1 - converted_size_mb/original_size_mb) * 100, 1)
            })
            
            # VALIDAÇÃO INTELIGENTE - APÓS conversão
            if converted_size_mb > self.max_converted_size_mb:
                error_msg = (
                    f"Áudio convertido muito grande para processamento!\n\n"
                    f"📁 Arquivo original: {original_size_mb:.1f}MB\n"
                    f"🎵 Áudio convertido: {converted_size_mb:.1f}MB\n"
                    f"🚫 Limite para transcrição: {self.max_converted_size_mb}MB\n\n"
                    f"💡 Soluções:\n"
                    f"• Enviar áudio mais curto (menos tempo)\n"
                    f"• Usar qualidade de gravação menor\n"
                    f"• Dividir em partes menores\n"
                    f"• Comprimir ainda mais antes de enviar"
                )
                
                logger.error("Converted audio exceeds processing limit", extra={
                    "original_size_mb": original_size_mb,
                    "converted_size_mb": converted_size_mb,
                    "limit_mb": self.max_converted_size_mb
                })
                
                raise AudioProcessingError(error_msg)
            
            if converted_size_mb > self.max_memory_size_mb:
                logger.warning("Audio file is very large, may cause memory issues", extra={
                    "converted_size_mb": converted_size_mb,
                    "memory_limit_mb": self.max_memory_size_mb
                })
            
            return mp3_bytes
            
        except AudioProcessingError:
            # Re-raise nossa exceção customizada
            raise
        except Exception as e:
            logger.error("Audio conversion failed", extra={
                "error": str(e),
                "original_size_mb": len(audio_bytes) / (1024 * 1024)
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
