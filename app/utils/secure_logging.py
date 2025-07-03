import re
import logging
from typing import Dict, Any, Optional
import json

class SecureLogFormatter(logging.Formatter):
    """Custom formatter that sanitizes sensitive data before logging"""
    
    # Patterns to detect and redact sensitive information
    SENSITIVE_PATTERNS = [
        # API Keys
        (re.compile(r'sk-[a-zA-Z0-9]{48}'), 'sk-***REDACTED***'),
        (re.compile(r'AIza[0-9A-Za-z-_]{35}'), 'AIza***REDACTED***'),
        
        # MongoDB connection strings
        (re.compile(r'mongodb(?:\+srv)?://[^:]+:[^@]+@'), 'mongodb://***REDACTED***@'),
        
        # Phone numbers (Brazilian format)
        (re.compile(r'\+55\d{10,11}'), '+55***REDACTED***'),
        (re.compile(r'\b55\d{10,11}\b'), '55***REDACTED***'),
        
        # Tokens and secrets
        (re.compile(r'[0-9]{10}:[A-Za-z0-9_-]{35}'), '***REDACTED_TOKEN***'),
        
        # Credit card numbers (basic pattern)
        (re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'), '****-****-****-****'),
        
        # Email addresses (partial redaction)
        (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '***@***.***'),
        
        # URLs with credentials
        (re.compile(r'https?://[^:]+:[^@]+@'), 'https://***REDACTED***@'),
        
        # Generic password patterns
        (re.compile(r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', re.IGNORECASE), 'password: ***REDACTED***'),
        (re.compile(r'pwd["\']?\s*[:=]\s*["\']?[^"\'\s]+', re.IGNORECASE), 'pwd: ***REDACTED***'),
        (re.compile(r'secret["\']?\s*[:=]\s*["\']?[^"\'\s]+', re.IGNORECASE), 'secret: ***REDACTED***'),
        (re.compile(r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', re.IGNORECASE), 'token: ***REDACTED***'),
        (re.compile(r'key["\']?\s*[:=]\s*["\']?[^"\'\s]+', re.IGNORECASE), 'key: ***REDACTED***'),
    ]
    
    def format(self, record: logging.LogRecord) -> str:
        # Format the message normally first
        formatted = super().format(record)
        
        # Sanitize sensitive data
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            formatted = pattern.sub(replacement, formatted)
        
        return formatted

class SecureLogger:
    """Utility class for secure logging with sensitive data redaction"""
    
    @staticmethod
    def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively sanitize dictionary data for logging"""
        if not isinstance(data, dict):
            return data
        
        sanitized = {}
        
        for key, value in data.items():
            key_lower = key.lower()
            
            # Check if key contains sensitive information
            if any(sensitive_key in key_lower for sensitive_key in [
                'password', 'secret', 'token', 'key', 'auth', 'credential'
            ]):
                sanitized[key] = '***REDACTED***'
            elif isinstance(value, dict):
                sanitized[key] = SecureLogger.sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    SecureLogger.sanitize_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            elif isinstance(value, str):
                sanitized[key] = SecureLogger.sanitize_string(value)
            else:
                sanitized[key] = value
        
        return sanitized
    
    @staticmethod
    def sanitize_string(text: str) -> str:
        """Sanitize string for logging"""
        if not isinstance(text, str):
            return text
        
        # Apply sensitive pattern replacements
        for pattern, replacement in SecureLogFormatter.SENSITIVE_PATTERNS:
            text = pattern.sub(replacement, text)
        
        return text
    
    @staticmethod
    def create_secure_extra(data: Dict[str, Any]) -> Dict[str, Any]:
        """Create secure extra data for logging"""
        return {
            'secure_data': SecureLogger.sanitize_dict(data)
        }
    
    @staticmethod
    def mask_phone_number(phone: str) -> str:
        """Mask phone number for logging"""
        if not phone or len(phone) < 4:
            return phone
        
        # Keep country code and last 4 digits
        if phone.startswith('+'):
            return f"+{phone[1:3]}***{phone[-4:]}"
        else:
            return f"{phone[:2]}***{phone[-4:]}"
    
    @staticmethod
    def mask_media_id(media_id: str) -> str:
        """Mask media ID for logging"""
        if not media_id or len(media_id) < 8:
            return media_id
        
        return f"{media_id[:4]}***{media_id[-4:]}"
    
    @staticmethod
    def safe_log_error(logger: logging.Logger, message: str, 
                      error: Exception, extra_data: Optional[Dict[str, Any]] = None):
        """Safely log error with sanitized data"""
        # Sanitize error message
        error_msg = SecureLogger.sanitize_string(str(error))
        
        # Create secure extra data
        extra = {'error': error_msg}
        if extra_data:
            extra.update(SecureLogger.sanitize_dict(extra_data))
        
        logger.error(message, extra=extra)
    
    @staticmethod
    def safe_log_info(logger: logging.Logger, message: str, 
                     extra_data: Optional[Dict[str, Any]] = None):
        """Safely log info with sanitized data"""
        extra = {}
        if extra_data:
            extra.update(SecureLogger.sanitize_dict(extra_data))
        
        logger.info(message, extra=extra)
    
    @staticmethod
    def safe_log_warning(logger: logging.Logger, message: str, 
                        extra_data: Optional[Dict[str, Any]] = None):
        """Safely log warning with sanitized data"""
        extra = {}
        if extra_data:
            extra.update(SecureLogger.sanitize_dict(extra_data))
        
        logger.warning(message, extra=extra)

def setup_secure_logging():
    """Setup secure logging configuration"""
    # Get root logger
    root_logger = logging.getLogger()
    
    # Create secure formatter
    secure_formatter = SecureLogFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Update existing handlers
    for handler in root_logger.handlers:
        handler.setFormatter(secure_formatter)
    
    # Create console handler with secure formatter if no handlers exist
    if not root_logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(secure_formatter)
        root_logger.addHandler(console_handler)
        root_logger.setLevel(logging.INFO)
    
    logging.info("Secure logging configured")

# Example usage patterns for developers
class LoggingExamples:
    """Examples of secure logging patterns to use throughout the application"""
    
    @staticmethod
    def log_user_interaction(logger: logging.Logger, phone: str, action: str):
        """Example: Log user interaction securely"""
        SecureLogger.safe_log_info(logger, f"User {action}", {
            'phone': SecureLogger.mask_phone_number(phone),
            'action': action,
            'timestamp': logging.Formatter().formatTime(logging.LogRecord(
                name='', level=0, pathname='', lineno=0, msg='', args=(), exc_info=None
            ))
        })
    
    @staticmethod
    def log_api_call(logger: logging.Logger, service: str, success: bool, 
                    response_time: float, error: Optional[str] = None):
        """Example: Log API call securely"""
        extra_data = {
            'service': service,
            'success': success,
            'response_time_ms': response_time * 1000
        }
        
        if error:
            extra_data['error'] = SecureLogger.sanitize_string(error)
        
        message = f"API call to {service} {'succeeded' if success else 'failed'}"
        SecureLogger.safe_log_info(logger, message, extra_data)
    
    @staticmethod
    def log_file_processing(logger: logging.Logger, file_type: str, 
                          file_size: int, duration: float):
        """Example: Log file processing securely"""
        SecureLogger.safe_log_info(logger, f"File processing completed", {
            'file_type': file_type,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'processing_duration_seconds': round(duration, 2)
        })