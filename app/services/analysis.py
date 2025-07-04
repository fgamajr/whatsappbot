from typing import Optional
import logging
from app.infrastructure.ai.gemini import GeminiService
from app.prompts.interview_analysis import INTERVIEW_ANALYSIS_PROMPT
from app.prompts.title_generation import TITLE_GENERATION_PROMPT
from app.core.exceptions import AnalysisError

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self):
        self.gemini = GeminiService()

    async def generate_title(self, snippet: str) -> Optional[str]:
        """Generate a concise title for a transcription snippet."""
        try:
            logger.info("Generating title for snippet", extra={"snippet_length": len(snippet)})
            title = await self.gemini.generate_analysis(
                transcript=snippet,
                prompt=TITLE_GENERATION_PROMPT
            )
            # Clean up the title, as the model might add quotes or newlines
            if title:
                return title.strip().replace('"', '')
            return None
        except Exception as e:
            logger.error("Title generation failed", extra={"error": str(e)})
            # We don't re-raise here to not break the main pipeline
            return None

    async def generate_report(self, transcript: str, prompt_text: Optional[str] = None) -> Optional[str]:
        """Generate comprehensive interview analysis using a specific prompt."""
        try:
            if not transcript or len(transcript.strip()) < 100:
                raise AnalysisError("Transcript too short for analysis")

            final_prompt = prompt_text or INTERVIEW_ANALYSIS_PROMPT

            logger.info("Generating interview analysis", extra={
                "transcript_length": len(transcript),
                "prompt_length": len(final_prompt)
            })

            analysis = await self.gemini.generate_analysis(
                transcript=transcript,
                prompt=final_prompt
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
