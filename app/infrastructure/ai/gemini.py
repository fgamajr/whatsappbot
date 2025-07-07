import google.generativeai as genai
from typing import Optional
import logging
from app.core.config import settings
from app.core.exceptions import AnalysisError

logger = logging.getLogger(__name__)


class GeminiService:
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(f'models/{settings.GEMINI_MODEL}')
        
    async def generate_analysis(self, transcript: str, prompt: str) -> Optional[str]:
        """Generate analysis using Gemini"""
        try:
            final_prompt = f"""TRANSCRIPT:
{transcript}

INSTRUCTIONS:
{prompt}"""
            
            logger.info("Starting Gemini analysis", extra={
                "transcript_length": len(transcript),
                "prompt_length": len(prompt)
            })
            
            response = self.model.generate_content(final_prompt)
            
            if response and response.text:
                logger.info("Gemini analysis completed", extra={
                    "response_length": len(response.text)
                })
                return response.text.strip()
            else:
                logger.warning("Gemini returned empty response")
                return None
                
        except Exception as e:
            logger.error("Gemini analysis failed", extra={
                "error": str(e)
            })
            raise AnalysisError(f"Failed to generate analysis: {str(e)}")
