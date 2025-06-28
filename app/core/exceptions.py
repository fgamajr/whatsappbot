"""Custom exceptions for the application"""


class InterviewBotException(Exception):
    """Base exception for the application"""
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class AudioProcessingError(InterviewBotException):
    """Error during audio processing"""
    pass


class TranscriptionError(InterviewBotException):
    """Error during transcription"""
    pass


class AnalysisError(InterviewBotException):
    """Error during analysis generation"""
    pass


class WhatsAppError(InterviewBotException):
    """Error with WhatsApp API"""
    pass


class DatabaseError(InterviewBotException):
    """Error with database operations"""
    pass


class ConfigurationError(InterviewBotException):
    """Error with configuration"""
    pass
