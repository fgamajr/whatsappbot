import asyncio
from app.celery_app import celery_app
from app.services.analysis import AnalysisService
from app.infrastructure.database.repositories.interview import InterviewRepository
import logging

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.generate_title_for_interview")
def generate_title_for_interview(interview_data: dict) -> dict:
    """
    Celery task to generate a title for an interview based on its transcription.
    """
    interview_id = interview_data.get("interview_id")
    if not interview_id:
        logger.error("interview_id not found in interview_data")
        return interview_data # Return original data

    try:
        logger.info(f"Starting title generation for interview_id: {interview_id}")
        interview_repo = InterviewRepository()
        interview = interview_repo.get_interview_by_id(interview_id)
        
        if not interview or not interview.transcription:
            logger.warning(f"Interview or transcription not found for id: {interview_id}")
            return interview_data

        snippet = " ".join(interview.transcription.split()[:1000])

        analysis_service = AnalysisService()
        # Run the async method in a sync context
        title = asyncio.run(analysis_service.generate_title(snippet))

        if title:
            interview_repo.update_interview(interview_id, {"title": title})
            interview_data["title"] = title
            logger.info(f"Successfully generated and saved title for interview_id: {interview_id}")
        else:
            logger.warning(f"Failed to generate title for interview_id: {interview_id}")
            interview_data["title"] = "Título não gerado"

    except Exception as e:
        logger.error(f"Error in title generation task for interview_id {interview_id}: {e}", exc_info=True)
        interview_data["title"] = "Erro ao gerar título"
    
    return interview_data
