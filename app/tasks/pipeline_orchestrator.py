from celery import chain, group, chord
from typing import Dict, Any
import logging
from app.tasks.audio_pipeline import (
    download_audio_task,
    convert_and_chunk_audio_task,
    transcribe_chunk_task,
    combine_transcripts_task,
)
from app.tasks.title_generation import generate_title_for_interview
from app.tasks.notification import notify_user_for_next_action
from app.utils.secure_logging import SecureLogger

logger = logging.getLogger(__name__)

def create_audio_processing_pipeline(message_data: Dict[str, Any]) -> chain:
    """
    Creates the initial audio processing pipeline.
    Flow: Download -> Chunk -> Transcribe (in parallel) -> Combine -> Generate Title -> Notify User
    """
    SecureLogger.safe_log_info(logger, "Creating audio processing pipeline", {
        'message_id': message_data.get('message_id'),
        'from_user': SecureLogger.mask_phone_number(message_data.get('from', ''))
    })

    # The pipeline is now a chain of tasks that ends with notifying the user.
    # The analysis and document generation are triggered by user interaction.
    pipeline = chain(
        download_audio_task.s(message_data),
        convert_and_chunk_audio_task.s(),
        create_parallel_transcription_workflow.s(),
        generate_title_for_interview.s(),
        notify_user_for_next_action.s()
    )
    
    SecureLogger.safe_log_info(logger, "Audio processing pipeline created", {
        'message_id': message_data.get('message_id'),
        'pipeline_steps': len(pipeline.tasks)
    })
    
    return pipeline

def create_parallel_transcription_workflow(interview_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a parallel transcription workflow using a chord.
    """
    if not interview_data or 'chunks_hex' not in interview_data:
        logger.error("Cannot create transcription workflow, interview_data is invalid.")
        raise ValueError("Invalid data received for transcription workflow.")

    SecureLogger.safe_log_info(logger, "Creating parallel transcription workflow", {
        'interview_id': interview_data.get('interview_id'),
        'chunks_count': len(interview_data.get('chunks_hex', []))
    })

    transcription_tasks = [
        transcribe_chunk_task.s({
            'chunk_hex': chunk_hex,
            'chunk_index': i,
            'interview_id': interview_data['interview_id'],
            'phone_number': interview_data['phone_number'],
            'total_chunks': interview_data['chunks_total']
        }) for i, chunk_hex in enumerate(interview_data['chunks_hex'])
    ]

    # Using a chord to run transcriptions in parallel and combine them after.
    transcription_chord = chord(
        group(transcription_tasks),
        combine_transcripts_task.s(interview_data)
    )

    result = transcription_chord.apply_async()
    return result.get() # Wait for the chord to complete.

def start_audio_processing(message_data: Dict[str, Any]) -> str:
    """
    Main entry point to start the audio processing pipeline.
    """
    SecureLogger.safe_log_info(logger, "Starting audio processing pipeline", {
        'message_id': message_data.get('message_id'),
        'from_user': SecureLogger.mask_phone_number(message_data.get('from', ''))
    })
    
    pipeline = create_audio_processing_pipeline(message_data)
    result = pipeline.apply_async()
    
    SecureLogger.safe_log_info(logger, "Audio processing pipeline started", {
        'pipeline_id': result.id,
        'message_id': message_data.get('message_id')
    })
    
    return result.id
