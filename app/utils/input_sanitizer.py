import re
import html
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class InputSanitizer:
    """Sanitize and validate user inputs for security"""
    
    # Maximum lengths for different input types
    MAX_TEXT_LENGTH = 4000  # WhatsApp message limit
    MAX_FILENAME_LENGTH = 255
    MAX_URL_LENGTH = 2048
    
    # Regex patterns for validation
    PHONE_NUMBER_PATTERN = re.compile(r'^[\d\s\-\+\(\)]+$')
    ALPHANUMERIC_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_\.]+$')
    
    # Dangerous patterns to detect
    SCRIPT_PATTERNS = [
        re.compile(r'<script.*?>.*?</script>', re.IGNORECASE | re.DOTALL),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'vbscript:', re.IGNORECASE),
        re.compile(r'on\w+\s*=', re.IGNORECASE),
    ]
    
    SQL_INJECTION_PATTERNS = [
        re.compile(r'(\bUNION\b|\bSELECT\b|\bINSERT\b|\bDELETE\b|\bDROP\b|\bCREATE\b)', re.IGNORECASE),
        re.compile(r'(\bOR\b|\bAND\b)\s+\d+\s*=\s*\d+', re.IGNORECASE),
        re.compile(r'[\'";]', re.IGNORECASE),
    ]
    
    @classmethod
    def sanitize_text_message(cls, text: str) -> str:
        """
        Sanitize text message content
        
        Args:
            text: Raw text message
            
        Returns:
            str: Sanitized text
            
        Raises:
            ValueError: If text is invalid or malicious
        """
        if not text or not isinstance(text, str):
            raise ValueError("Text must be a non-empty string")
        
        # Length validation
        if len(text) > cls.MAX_TEXT_LENGTH:
            raise ValueError(f"Text exceeds maximum length of {cls.MAX_TEXT_LENGTH}")
        
        # Remove null bytes and control characters
        sanitized = text.replace('\x00', '').replace('\r', '').strip()
        
        # HTML escape to prevent XSS
        sanitized = html.escape(sanitized)
        
        # Check for dangerous patterns
        cls._check_dangerous_patterns(sanitized)
        
        return sanitized
    
    @classmethod
    def sanitize_phone_number(cls, phone: str) -> str:
        """
        Sanitize phone number input
        
        Args:
            phone: Raw phone number
            
        Returns:
            str: Sanitized phone number
            
        Raises:
            ValueError: If phone number is invalid
        """
        if not phone or not isinstance(phone, str):
            raise ValueError("Phone number must be a non-empty string")
        
        # Remove whitespace and normalize
        sanitized = phone.strip()
        
        # Length validation
        if len(sanitized) > 20:  # International phone numbers shouldn't exceed 20 digits
            raise ValueError("Phone number too long")
        
        # Pattern validation
        if not cls.PHONE_NUMBER_PATTERN.match(sanitized):
            raise ValueError("Phone number contains invalid characters")
        
        return sanitized
    
    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Sanitize filename for safe storage
        
        Args:
            filename: Raw filename
            
        Returns:
            str: Sanitized filename
            
        Raises:
            ValueError: If filename is invalid
        """
        if not filename or not isinstance(filename, str):
            raise ValueError("Filename must be a non-empty string")
        
        # Remove path traversal characters
        sanitized = filename.replace('..', '').replace('/', '').replace('\\', '')
        
        # Length validation
        if len(sanitized) > cls.MAX_FILENAME_LENGTH:
            raise ValueError(f"Filename exceeds maximum length of {cls.MAX_FILENAME_LENGTH}")
        
        # Pattern validation (alphanumeric, dots, hyphens, underscores)
        if not cls.ALPHANUMERIC_PATTERN.match(sanitized):
            raise ValueError("Filename contains invalid characters")
        
        return sanitized
    
    @classmethod
    def sanitize_media_id(cls, media_id: str) -> str:
        """
        Sanitize media ID from WhatsApp
        
        Args:
            media_id: Raw media ID
            
        Returns:
            str: Sanitized media ID
            
        Raises:
            ValueError: If media ID is invalid
        """
        if not media_id or not isinstance(media_id, str):
            raise ValueError("Media ID must be a non-empty string")
        
        # WhatsApp media IDs are typically alphanumeric
        sanitized = media_id.strip()
        
        # Length validation (WhatsApp media IDs are usually reasonable length)
        if len(sanitized) > 200:
            raise ValueError("Media ID too long")
        
        # Pattern validation - only alphanumeric and some special chars
        if not re.match(r'^[a-zA-Z0-9\-_]+$', sanitized):
            raise ValueError("Media ID contains invalid characters")
        
        return sanitized
    
    @classmethod
    def validate_webhook_data(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and sanitize webhook data structure
        
        Args:
            data: Raw webhook data
            
        Returns:
            Dict: Sanitized webhook data
            
        Raises:
            ValueError: If data structure is invalid
        """
        if not isinstance(data, dict):
            raise ValueError("Webhook data must be a dictionary")
        
        # Validate required structure
        if "entry" not in data:
            raise ValueError("Missing 'entry' field in webhook data")
        
        if not isinstance(data["entry"], list) or not data["entry"]:
            raise ValueError("'entry' field must be a non-empty list")
        
        # Validate entry structure
        entry = data["entry"][0]
        if not isinstance(entry, dict):
            raise ValueError("Entry must be a dictionary")
        
        if "changes" not in entry:
            raise ValueError("Missing 'changes' field in entry")
        
        if not isinstance(entry["changes"], list) or not entry["changes"]:
            raise ValueError("'changes' field must be a non-empty list")
        
        # Basic sanitization - remove any null bytes from string values
        sanitized_data = cls._deep_sanitize_dict(data)
        
        return sanitized_data
    
    @classmethod
    def _check_dangerous_patterns(cls, text: str) -> None:
        """Check for dangerous patterns in text"""
        # Check for script injection
        for pattern in cls.SCRIPT_PATTERNS:
            if pattern.search(text):
                logger.warning("Potential script injection detected", extra={
                    "pattern": pattern.pattern,
                    "text_preview": text[:100]
                })
                raise ValueError("Text contains potentially dangerous script content")
        
        # Check for SQL injection
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if pattern.search(text):
                logger.warning("Potential SQL injection detected", extra={
                    "pattern": pattern.pattern,
                    "text_preview": text[:100]
                })
                raise ValueError("Text contains potentially dangerous SQL content")
    
    @classmethod
    def _deep_sanitize_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively sanitize dictionary values"""
        sanitized = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                # Remove null bytes and control characters
                sanitized[key] = value.replace('\x00', '').replace('\r', '')
            elif isinstance(value, dict):
                sanitized[key] = cls._deep_sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    cls._deep_sanitize_dict(item) if isinstance(item, dict) 
                    else item.replace('\x00', '').replace('\r', '') if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                sanitized[key] = value
        
        return sanitized
    
    @classmethod
    def validate_url(cls, url: str) -> str:
        """
        Validate and sanitize URL
        
        Args:
            url: Raw URL
            
        Returns:
            str: Sanitized URL
            
        Raises:
            ValueError: If URL is invalid
        """
        if not url or not isinstance(url, str):
            raise ValueError("URL must be a non-empty string")
        
        # Length validation
        if len(url) > cls.MAX_URL_LENGTH:
            raise ValueError(f"URL exceeds maximum length of {cls.MAX_URL_LENGTH}")
        
        # Parse URL to validate structure
        try:
            parsed = urlparse(url)
            
            # Validate scheme
            if parsed.scheme not in ('http', 'https'):
                raise ValueError("URL must use HTTP or HTTPS scheme")
            
            # Validate hostname
            if not parsed.netloc:
                raise ValueError("URL must have a valid hostname")
            
            return url
            
        except Exception as e:
            raise ValueError(f"Invalid URL format: {str(e)}")