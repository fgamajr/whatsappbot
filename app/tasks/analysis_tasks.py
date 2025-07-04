import logging
import asyncio
from app.celery_app import celery_app
from app.services.analysis import AnalysisService
from app.services.document_generator import DocumentGenerator
from app.infrastructure.database.repositories.interview import InterviewRepository
from app.infrastructure.messaging.factory import get_messaging_service
from app.domain.entities.interview import InterviewStatus

logger = logging.getLogger(__name__)

@celery_app.task(name="tasks.start_analysis_pipeline")
def start_analysis_pipeline(interview_id: str, prompt_text: str):
    """
    Celery task to run the analysis and document generation part of the pipeline.
    """
    try:
        logger.info(f"Starting analysis pipeline for interview: {interview_id}")
        interview_repo = InterviewRepository()
        interview = interview_repo.get_interview_by_id(interview_id)

        if not interview or not interview.transcription:
            logger.error(f"Interview or transcription not found for analysis: {interview_id}")
            return

        # Update status to ANALYZING
        interview_repo.update_interview(interview_id, {"status": InterviewStatus.ANALYZING.value})

        analysis_service = AnalysisService()
        analysis = asyncio.run(analysis_service.generate_report(interview.transcription, prompt_text))

        if analysis:
            interview_repo.update_interview(interview_id, {"analysis": analysis})
            interview.analysis = analysis # Update local object for doc generation

        # Generate and send documents
        doc_generator = DocumentGenerator()
        messaging_service = get_messaging_service()

        transcript_path, analysis_path = doc_generator.create_documents(
            interview.transcription,
            interview.analysis or "Análise não disponível",
            interview.id
        )

        async def send_docs_async():
            await messaging_service.send_document(interview.phone_number, transcript_path, f"Transcrição - {interview.title}.docx")
            if interview.analysis and analysis_path:
                await messaging_service.send_document(interview.phone_number, analysis_path, f"Análise - {interview.title}.docx")

        asyncio.run(send_docs_async())

        # Final status update
        interview_repo.update_interview(interview_id, {"status": InterviewStatus.COMPLETED.value})
        logger.info(f"Successfully completed analysis pipeline for interview: {interview_id}")

    except Exception as e:
        logger.error(f"Analysis pipeline failed for interview {interview_id}: {e}", exc_info=True)
        interview_repo.update_interview(interview_id, {"status": InterviewStatus.FAILED.value, "error_message": str(e)})
