import openai
import httpx
from typing import Optional, Dict
import logging
import io
import traceback  # Import for detailed error printing
from app.core.config import settings
from app.core.exceptions import TranscriptionError

logger = logging.getLogger(__name__)


class WhisperService:
    """
    Service to interact with the OpenAI Whisper API for audio transcription.
    """
    def __init__(self):
        """
        Initializes the asynchronous OpenAI client.
        
        An explicit httpx.AsyncClient is passed to avoid potential issues
        with proxy configurations that the default client might pick up.
        """
        self.client = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            http_client=httpx.AsyncClient()
        )
        
    async def transcribe(
        self, 
        audio_bytes: bytes,
        language: str = "pt",
        response_format: str = "verbose_json"
    ) -> Dict:
        """
        Transcribes an audio file using the Whisper API.

        This function sends the audio bytes to OpenAI and returns a structured
        dictionary with the full transcript and timestamped segments.

        Args:
            audio_bytes: The audio content in bytes.
            language: The language of the audio (ISO 639-1 format).
            response_format: The desired format for the response. 'verbose_json'
                             provides detailed segments and timestamps.

        Returns:
            A dictionary containing the transcription text and segments.
        
        Raises:
            TranscriptionError: If the transcription fails at any stage.
        """
        try:
            # The OpenAI API requires a file-like object with a name.
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "audio.mp3"

            logger.info("Starting Whisper transcription", extra={
                "audio_size_bytes": len(audio_bytes),
                "language": language
            })

            # Create the transcription request
            response = await self.client.audio.transcriptions.create(
                model=settings.WHISPER_MODEL, # Using model from config for flexibility
                file=audio_file,
                language=language,
                response_format=response_format,
            )

            # Structure the result
            result = {
                "text": response.text,
                "segments": getattr(response, 'segments', [])
            }

            logger.info("Whisper transcription completed successfully", extra={
                "text_length": len(result["text"]),
                "segments_count": len(result["segments"])
            })

            return result

        # Catches specific API errors from OpenAI (e.g., invalid key, no credits)
        except openai.APIStatusError as e:
            # --- Detailed tracing for API errors is active ---
            print("\n\n================================================")
            print("🚨 Tipo: API Error (auth/billing/quota)")
            traceback.print_exc()
            print("================================================\n\n")
            
            logger.error(
                "Whisper transcription failed due to OpenAI API error",
                extra={
                    "status_code": e.status_code,
                    "error_message": str(e),
                    "response_body": e.body, 
                }
            )
            raise TranscriptionError(f"OpenAI API Error: {str(e)}")

        # Catches any other unexpected errors (e.g., network issues)
        except Exception as e:
            # --- Detailed tracing for unexpected errors is active ---
            print("\n\n================================================")
            print("🚨 Tipo: Unexpected Error (network/etc)")
            traceback.print_exc()
            print("================================================\n\n")

            logger.error(
                "Whisper transcription failed due to an unexpected error",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                }
            )
            raise TranscriptionError(f"Unexpected error during transcription: {str(e)}")

