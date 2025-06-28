from typing import List, Tuple
from pydantic import BaseModel


class AudioChunk(BaseModel):
    index: int
    start_time_minutes: float
    duration_minutes: float
    size_bytes: int
    
    
class AudioFile(BaseModel):
    media_id: str
    size_mb: float
    duration_minutes: Optional[float] = None
    format: str = "audio/ogg"
    chunks: List[AudioChunk] = []
    
    def add_chunk(self, chunk: AudioChunk):
        self.chunks.append(chunk)
    
    @property
    def total_chunks(self) -> int:
        return len(self.chunks)
