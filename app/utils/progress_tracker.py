import asyncio
import time
from typing import Optional, Callable
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ProgressTracker:
    """Manages progress tracking and heartbeat messages during long operations"""
    
    def __init__(self, messaging_provider, phone_number: str):
        self.messaging_provider = messaging_provider
        self.phone_number = phone_number
        self.heartbeat_interval = 90  # seconds (reduced frequency)
        self.last_message_time = 0
        self.min_message_interval = 30  # minimum seconds between messages (increased)
        
    async def send_progress_message(self, message: str, force: bool = False):
        """Send progress message with rate limiting"""
        current_time = time.time()
        
        if force or (current_time - self.last_message_time) >= self.min_message_interval:
            await self.messaging_provider.send_text_message(
                self.phone_number,
                message
            )
            self.last_message_time = current_time
            logger.info("Progress message sent", extra={
                "phone_number": self.phone_number,
                "message_preview": message[:50] + "..." if len(message) > 50 else message
            })
    
    async def run_with_heartbeat(self, operation: Callable, operation_name: str, 
                               estimated_minutes: Optional[float] = None):
        """Run operation with periodic heartbeat messages"""
        start_time = time.time()
        heartbeat_task = None
        
        try:
            # Send initial message with estimate (more concise)
            initial_msg = f"🔄 {operation_name}"
            if estimated_minutes and estimated_minutes > 1:
                initial_msg += f" (~{estimated_minutes:.1f}min)"
            
            await self.send_progress_message(initial_msg, force=True)
            
            # Start heartbeat task
            heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(operation_name, estimated_minutes)
            )
            
            # Run the actual operation
            result = await operation()
            
            # Cancel heartbeat and send completion message
            if heartbeat_task:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            elapsed_time = time.time() - start_time
            completion_msg = f"✅ {operation_name} concluído!"
            # Only show timing for longer operations
            if elapsed_time > 45:
                if elapsed_time > 60:
                    completion_msg += f" ({elapsed_time/60:.1f}min)"
                else:
                    completion_msg += f" ({elapsed_time:.0f}s)"
            
            await self.send_progress_message(completion_msg, force=True)
            
            return result
            
        except Exception as e:
            # Cancel heartbeat on error
            if heartbeat_task:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            elapsed_time = time.time() - start_time
            error_msg = f"❌ {operation_name} falhou após {elapsed_time:.0f}s"
            await self.send_progress_message(error_msg, force=True)
            raise
    
    async def _heartbeat_loop(self, operation_name: str, estimated_minutes: Optional[float]):
        """Periodic heartbeat messages during long operations"""
        try:
            start_time = time.time()
            message_count = 0
            
            while True:
                await asyncio.sleep(self.heartbeat_interval)
                
                elapsed_time = time.time() - start_time
                elapsed_minutes = elapsed_time / 60
                
                message_count += 1
                
                # Create heartbeat message
                heartbeat_msg = f"⏳ {operation_name} em progresso..."
                
                if elapsed_minutes < 1:
                    heartbeat_msg += f"\n⌛ {elapsed_time:.0f}s decorridos"
                else:
                    heartbeat_msg += f"\n⌛ {elapsed_minutes:.1f}min decorridos"
                
                # Add estimated time remaining
                if estimated_minutes and elapsed_minutes < estimated_minutes:
                    remaining = estimated_minutes - elapsed_minutes
                    if remaining > 0:
                        if remaining < 1:
                            heartbeat_msg += f"\n🎯 Restam ~{remaining * 60:.0f}s"
                        else:
                            heartbeat_msg += f"\n🎯 Restam ~{remaining:.1f}min"
                
                # Add encouraging message less frequently
                if message_count % 2 == 0:
                    heartbeat_msg += f"\n💪 Ainda processando..."
                
                await self.send_progress_message(heartbeat_msg)
                
        except asyncio.CancelledError:
            logger.info("Heartbeat cancelled", extra={
                "operation": operation_name,
                "elapsed_seconds": time.time() - start_time
            })
            raise


class TimeEstimator:
    """Estimates processing times based on audio characteristics"""
    
    @staticmethod
    def estimate_conversion_time(audio_size_mb: float) -> float:
        """Estimate audio conversion time in minutes"""
        # Based on typical pydub performance: ~1-2 seconds per MB
        base_time = audio_size_mb * 1.5 / 60  # minutes
        return max(0.1, base_time)  # minimum 6 seconds
    
    @staticmethod
    def estimate_transcription_time(audio_duration_minutes: float, chunk_size_mb: float) -> float:
        """Estimate Whisper transcription time in minutes"""
        # Whisper typically processes 1 minute of audio in 10-20 seconds
        # But API calls add overhead, so we use more conservative estimates
        base_time = audio_duration_minutes * 0.4  # 24 seconds per minute of audio
        
        # Add API overhead (network, queue time)
        api_overhead = 0.5  # 30 seconds base overhead
        
        # Larger chunks take slightly longer due to processing complexity
        size_factor = 1.0 + (chunk_size_mb / 25) * 0.3  # up to 30% more for large chunks
        
        total_time = (base_time + api_overhead) * size_factor
        return max(0.5, total_time)  # minimum 30 seconds
    
    @staticmethod
    def estimate_analysis_time(transcript_length: int) -> float:
        """Estimate Gemini analysis time in minutes"""
        # Gemini typically processes ~1000 characters per second
        # But we add conservative buffer for API calls
        base_time = transcript_length / 2000 / 60  # minutes
        api_overhead = 0.3  # 20 seconds base overhead
        
        total_time = base_time + api_overhead
        return max(0.2, total_time)  # minimum 12 seconds
    
    @staticmethod
    def estimate_document_generation_time(transcript_length: int, has_analysis: bool) -> float:
        """Estimate document generation time in minutes"""
        # Document generation is relatively fast
        base_time = transcript_length / 10000 / 60  # minutes (very fast)
        
        if has_analysis:
            base_time *= 2  # double time for analysis document
        
        return max(0.1, base_time)  # minimum 6 seconds
    
    @staticmethod
    def estimate_total_processing_time(audio_size_mb: float, audio_duration_minutes: float) -> dict:
        """Estimate total processing time breakdown"""
        conversion_time = TimeEstimator.estimate_conversion_time(audio_size_mb)
        
        # Estimate number of chunks
        chunk_duration = 15  # minutes per chunk
        num_chunks = max(1, int(audio_duration_minutes / chunk_duration) + 1)
        
        # Transcription time per chunk
        avg_chunk_duration = audio_duration_minutes / num_chunks
        avg_chunk_size = audio_size_mb / num_chunks
        transcription_per_chunk = TimeEstimator.estimate_transcription_time(avg_chunk_duration, avg_chunk_size)
        total_transcription_time = transcription_per_chunk * num_chunks
        
        # Analysis time (estimate based on expected transcript length)
        # Rough estimate: 1 minute of audio = 150 words = 1000 characters
        estimated_transcript_length = audio_duration_minutes * 1000
        analysis_time = TimeEstimator.estimate_analysis_time(estimated_transcript_length)
        
        # Document generation
        document_time = TimeEstimator.estimate_document_generation_time(estimated_transcript_length, True)
        
        total_time = conversion_time + total_transcription_time + analysis_time + document_time
        
        return {
            "conversion_minutes": conversion_time,
            "transcription_minutes": total_transcription_time,
            "transcription_per_chunk_minutes": transcription_per_chunk,
            "analysis_minutes": analysis_time,
            "document_minutes": document_time,
            "total_minutes": total_time,
            "num_chunks": num_chunks
        }