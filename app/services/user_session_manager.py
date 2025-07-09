from typing import Optional, Dict, Any
import logging
from app.domain.entities.user_session import UserSession, SessionState
from app.infrastructure.database.repositories.user_session import UserSessionRepository

logger = logging.getLogger(__name__)


class UserSessionManager:
    """Service for managing user session states"""
    
    def __init__(self):
        self.session_repo = UserSessionRepository()
    
    async def get_or_create_session(self, user_id: str) -> UserSession:
        """Get existing session or create new one"""
        try:
            session = await self.session_repo.get_session(user_id)
            
            if not session:
                session = UserSession(user_id=user_id)
                await self.session_repo.save_session(session)
                logger.info("Created new user session", extra={
                    "user_id": user_id
                })
            
            return session
            
        except Exception as e:
            logger.error("Failed to get or create session", extra={
                "error": str(e),
                "user_id": user_id
            })
            # Return default session as fallback
            return UserSession(user_id=user_id)

    async def set_user_busy(self, user_id: str, task_description: str) -> bool:
        """Set user to busy state"""
        try:
            session = await self.get_or_create_session(user_id)
            session.set_state(SessionState.BUSY, {"task": task_description})
            await self.session_repo.save_session(session)
            logger.info("User set to BUSY state", extra={"user_id": user_id, "task": task_description})
            return True
        except Exception as e:
            logger.error("Failed to set user to busy state", extra={"error": str(e), "user_id": user_id})
            return False
    
    async def set_waiting_for_custom_instructions(self, user_id: str, prompt_id: str) -> bool:
        """Set user to waiting for custom instructions state"""
        try:
            session = await self.get_or_create_session(user_id)
            
            session.set_state(SessionState.WAITING_CUSTOM_INSTRUCTIONS, {
                "custom_prompt_id": prompt_id,
                "step": "instructions"
            })
            
            await self.session_repo.save_session(session)
            
            logger.info("User set to waiting for custom instructions", extra={
                "user_id": user_id,
                "prompt_id": prompt_id
            })
            
            return True
            
        except Exception as e:
            logger.error("Failed to set waiting for custom instructions", extra={
                "error": str(e),
                "user_id": user_id
            })
            return False
    
    async def set_waiting_for_youtube_confirmation(self, user_id: str, video_data: bytes, metadata: dict) -> bool:
        """Set user to waiting for YouTube video processing confirmation"""
        try:
            import tempfile
            import os
            
            # Store video data in a temporary file
            temp_fd, temp_path = tempfile.mkstemp(suffix='.tmp', prefix='youtube_')
            with os.fdopen(temp_fd, 'wb') as temp_file:
                temp_file.write(video_data)
            
            session = await self.get_or_create_session(user_id)
            
            session.set_state(SessionState.WAITING_YOUTUBE_CONFIRMATION, {
                "metadata": metadata,
                "step": "confirmation",
                "video_size": len(video_data),
                "temp_file_path": temp_path
            })
            
            await self.session_repo.save_session(session)
            
            logger.info("User set to waiting for YouTube confirmation", extra={
                "user_id": user_id,
                "video_title": metadata.get('title'),
                "file_size": len(video_data)
            })
            
            return True
            
        except Exception as e:
            logger.error("Failed to set waiting for YouTube confirmation", extra={
                "error": str(e),
                "user_id": user_id
            })
            return False
    
    async def is_waiting_for_youtube_confirmation(self, user_id: str) -> bool:
        """Check if user is waiting for YouTube processing confirmation"""
        try:
            session = await self.session_repo.get_session(user_id)
            return session and session.state == SessionState.WAITING_YOUTUBE_CONFIRMATION
        except Exception as e:
            logger.error("Failed to check YouTube confirmation state", extra={
                "error": str(e),
                "user_id": user_id
            })
            return False
    
    async def process_youtube_confirmation(self, user_id: str, confirmed: bool) -> tuple[bool, dict]:
        """Process YouTube confirmation response"""
        try:
            session = await self.session_repo.get_session(user_id)
            
            if not session or session.state != SessionState.WAITING_YOUTUBE_CONFIRMATION:
                return False, {}
            
            if confirmed:
                # Get video data from temporary file
                import os
                temp_file_path = session.context.get("temp_file_path")
                metadata = session.context.get("metadata", {})
                
                video_data = None
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        with open(temp_file_path, 'rb') as f:
                            video_data = f.read()
                        # Clean up temp file
                        os.unlink(temp_file_path)
                    except Exception as e:
                        logger.error("Failed to read temp file", extra={
                            "error": str(e),
                            "temp_file_path": temp_file_path
                        })
                
                # Clear session state
                session.clear_state()
                await self.session_repo.save_session(session)
                
                logger.info("YouTube processing confirmed", extra={
                    "user_id": user_id,
                    "video_title": metadata.get('title')
                })
                
                return True, {"video_data": video_data, "metadata": metadata}
            else:
                # User declined, clean up temp file and clear session
                import os
                temp_file_path = session.context.get("temp_file_path")
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.unlink(temp_file_path)
                    except Exception as e:
                        logger.error("Failed to clean up temp file", extra={
                            "error": str(e),
                            "temp_file_path": temp_file_path
                        })
                
                session.clear_state()
                await self.session_repo.save_session(session)
                
                logger.info("YouTube processing declined", extra={
                    "user_id": user_id
                })
                
                return True, {"declined": True}
                
        except Exception as e:
            logger.error("Failed to process YouTube confirmation", extra={
                "error": str(e),
                "user_id": user_id
            })
            return False, {}
    
    async def process_custom_instructions(self, user_id: str, instructions: str) -> Optional[str]:
        """Process custom instructions and return prompt ID if ready"""
        try:
            session = await self.get_or_create_session(user_id)
            
            if session.state != SessionState.WAITING_CUSTOM_INSTRUCTIONS:
                return None
            
            # Save instructions and set waiting for audio
            session.set_state(SessionState.WAITING_AUDIO, {
                "custom_prompt_id": session.get_context_value("custom_prompt_id"),
                "custom_instructions": instructions,
                "step": "audio"
            })
            
            await self.session_repo.save_session(session)
            
            logger.info("Custom instructions processed", extra={
                "user_id": user_id,
                "instructions_length": len(instructions)
            })
            
            return session.get_context_value("custom_prompt_id")
            
        except Exception as e:
            logger.error("Failed to process custom instructions", extra={
                "error": str(e),
                "user_id": user_id
            })
            return None
    
    async def get__instructions(self, user_id: str) -> Optional[str]:
        """Get stored custom instructions for user"""
        try:
            session = await self.session_repo.get_session(user_id)
            
            if not session:
                return None
            
            return session.get_context_value("custom_instructions")
            
        except Exception as e:
            logger.error("Failed to get custom instructions", extra={
                "error": str(e),
                "user_id": user_id
            })
            return None
    
    async def clear_session(self, user_id: str) -> bool:
        """Clear user session"""
        try:
            session = await self.session_repo.get_session(user_id)
            
            if session:
                session.clear_state()
                await self.session_repo.save_session(session)
                
                logger.info("User session cleared", extra={
                    "user_id": user_id
                })
            
            return True
            
        except Exception as e:
            logger.error("Failed to clear session", extra={
                "error": str(e),
                "user_id": user_id
            })
            return False
    
    async def is_waiting_for_audio(self, user_id: str) -> bool:
        """Check if user is waiting to send audio"""
        try:
            session = await self.session_repo.get_session(user_id)
            return session and session.state == SessionState.WAITING_AUDIO
            
        except Exception as e:
            logger.error("Failed to check waiting for audio", extra={
                "error": str(e),
                "user_id": user_id
            })
            return False
    
    async def is_waiting_for_custom_instructions(self, user_id: str) -> bool:
        """Check if user is waiting to provide custom instructions"""
        try:
            session = await self.session_repo.get_session(user_id)
            return session and session.state == SessionState.WAITING_CUSTOM_INSTRUCTIONS
            
        except Exception as e:
            logger.error("Failed to check waiting for instructions", extra={
                "error": str(e),
                "user_id": user_id
            })
            return False