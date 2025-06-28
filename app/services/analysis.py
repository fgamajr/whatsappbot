from typing import Optional
import logging
from app.infrastructure.ai.gemini import GeminiService
from app.prompts.interview_analysis import INTERVIEW_ANALYSIS_PROMPT
from app.core.exceptions import AnalysisError

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self):
        self.gemini = GeminiService()
    
    async def generate_report(self, transcript: str) -> Optional[str]:
        """Generate comprehensive interview analysis"""
        try:
            if not transcript or len(transcript.strip()) < 100:
                raise AnalysisError("Transcript too short for analysis")
            
            logger.info("Generating interview analysis", extra={
                "transcript_length": len(transcript)
            })
            
            analysis = await self.gemini.generate_analysis(
                transcript=transcript,
                prompt=INTERVIEW_ANALYSIS_PROMPT
            )
            
            if analysis:
                logger.info("Analysis generated successfully", extra={
                    "analysis_length": len(analysis)
                })
            
            return analysis
            
        except Exception as e:
            logger.error("Analysis generation failed", extra={
                "error": str(e)
            })
            raise AnalysisError(f"Failed to generate analysis: {str(e)}")
