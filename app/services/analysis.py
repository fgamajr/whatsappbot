from typing import Optional
import logging
import time
from app.infrastructure.ai.gemini import GeminiService
from app.services.prompt_manager import PromptManagerService
from app.domain.entities.prompt import PromptCategory
from app.core.exceptions import AnalysisError

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self):
        self.gemini = GeminiService()
        self.prompt_manager = PromptManagerService()
        logger.info("AnalysisService initialized")
    
    async def generate_report(self, transcript: str, user_id: Optional[str] = None, 
                            prompt_identifier: Optional[str] = None,
                            custom_instructions: Optional[str] = None) -> Optional[str]:
        """Generate interview analysis using selected or default prompt"""
        try:
            if not transcript or len(transcript.strip()) < 100:
                raise AnalysisError("Transcript too short for analysis")
            
            transcript_length = len(transcript)
            word_count = len(transcript.split())
            
            logger.info("Starting interview analysis", extra={
                "transcript_length": transcript_length,
                "word_count": word_count,
                "user_id": user_id,
                "prompt_identifier": prompt_identifier
            })
            
            # Get the prompt to use
            prompt_template = None
            
            if prompt_identifier and user_id:
                # User specified a prompt (could be ID or short code)
                if len(prompt_identifier) > 10:  # Likely a prompt ID
                    prompt_template = await self.prompt_manager.prompt_repo.get_by_id(prompt_identifier)
                else:
                    # Short code or number
                    prompt_template = await self.prompt_manager.select_prompt_for_user(
                        user_id, prompt_identifier
                    )
            elif user_id:
                # Use user's default or most popular
                prompt_template = await self.prompt_manager.get_user_default_or_popular(
                    user_id, PromptCategory.INTERVIEW_ANALYSIS
                )
            else:
                # Fallback to most popular prompt
                prompt_template = await self.prompt_manager.get_default_prompt_for_category(
                    PromptCategory.INTERVIEW_ANALYSIS
                )
            
            if not prompt_template:
                raise AnalysisError("No suitable prompt template found")
            
            logger.info("Using prompt template", extra={
                "prompt_id": prompt_template.id,
                "prompt_name": prompt_template.name,
                "prompt_category": prompt_template.category,
                "prompt_identifier_received": prompt_identifier,
                "user_id": user_id
            })
            
            # Format the prompt with transcript and custom instructions if needed
            format_kwargs = {"transcript": transcript}
            
            # Add custom instructions if this is a custom prompt
            if prompt_template.short_code == "custom" and custom_instructions:
                format_kwargs["custom_instructions"] = custom_instructions
                
                logger.info("Using custom instructions", extra={
                    "prompt_id": prompt_template.id,
                    "instructions_length": len(custom_instructions),
                    "user_id": user_id
                })
            elif prompt_template.short_code == "custom":
                # Custom prompt without instructions - use default
                format_kwargs["custom_instructions"] = (
                    "Faça uma análise geral e abrangente da entrevista, "
                    "destacando os pontos mais relevantes mencionados."
                )
                
                logger.warning("Custom prompt used without instructions, using default", extra={
                    "prompt_id": prompt_template.id,
                    "user_id": user_id
                })
            
            formatted_prompt = await self.prompt_manager.format_prompt_for_analysis(
                prompt_template, **format_kwargs
            )
            
            # Record API call timing
            api_start_time = time.time()
            
            analysis = await self.gemini.generate_analysis(
                transcript=transcript,
                prompt=formatted_prompt
            )
            
            api_duration = time.time() - api_start_time
            
            if analysis:
                logger.info("Analysis generated successfully", extra={
                    "analysis_length": len(analysis),
                    "api_duration_seconds": api_duration,
                    "transcript_length": transcript_length,
                    "processing_rate_chars_per_second": transcript_length / api_duration if api_duration > 0 else 0,
                    "prompt_used": prompt_template.name
                })
            else:
                logger.warning("Analysis generation returned empty result", extra={
                    "api_duration_seconds": api_duration,
                    "transcript_length": transcript_length,
                    "prompt_used": prompt_template.name
                })
            
            return analysis
            
        except Exception as e:
            logger.error("Analysis generation failed", extra={
                "error": str(e),
                "transcript_length": len(transcript) if transcript else 0
            })
            raise AnalysisError(f"Failed to generate analysis: {str(e)}")
