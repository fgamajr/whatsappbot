import hmac
import hashlib
import logging
from fastapi import Request, HTTPException
from app.core.config import settings

logger = logging.getLogger(__name__)

class WebhookSecurityValidator:
    """Validates webhook signatures for enhanced security"""
    
    @staticmethod
    async def verify_whatsapp_signature(request: Request, body: bytes) -> bool:
        """
        Verify WhatsApp webhook signature using HMAC-SHA256
        
        Args:
            request: FastAPI request object
            body: Raw request body bytes
            
        Returns:
            bool: True if signature is valid
            
        Raises:
            HTTPException: If signature verification fails
        """
        try:
            # Get signature from header
            signature_header = request.headers.get("X-Hub-Signature-256")
            
            if not signature_header:
                logger.warning("Missing webhook signature header")
                raise HTTPException(status_code=401, detail="Missing signature")
            
            # Extract signature (remove 'sha256=' prefix)
            if not signature_header.startswith("sha256="):
                logger.warning("Invalid signature format")
                raise HTTPException(status_code=401, detail="Invalid signature format")
            
            received_signature = signature_header[7:]  # Remove 'sha256=' prefix
            
            # Calculate expected signature
            expected_signature = hmac.new(
                settings.WHATSAPP_WEBHOOK_SECRET.encode('utf-8'),
                body,
                hashlib.sha256
            ).hexdigest()
            
            # Secure comparison to prevent timing attacks
            if not hmac.compare_digest(received_signature, expected_signature):
                logger.warning("Invalid webhook signature", extra={
                    "received_signature": received_signature[:10] + "...",  # Log partial for debugging
                    "source_ip": request.client.host if request.client else "unknown"
                })
                raise HTTPException(status_code=401, detail="Invalid signature")
            
            logger.info("Webhook signature verified successfully")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Signature verification error", extra={
                "error": str(e),
                "source_ip": request.client.host if request.client else "unknown"
            })
            raise HTTPException(status_code=500, detail="Signature verification failed")
    
    @staticmethod
    async def verify_telegram_signature(request: Request, body: bytes) -> bool:
        """
        Verify Telegram webhook signature
        
        Args:
            request: FastAPI request object
            body: Raw request body bytes
            
        Returns:
            bool: True if signature is valid
        """
        try:
            # Telegram uses a different approach - token validation
            # This is a simplified version, adjust based on your Telegram setup
            
            # For Telegram, you might want to validate the bot token in the URL path
            # or use a secret token header if you've configured one
            
            secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            
            if secret_token and secret_token == settings.TELEGRAM_WEBHOOK_SECRET:
                logger.info("Telegram webhook signature verified")
                return True
            
            # If no secret token is configured, you might skip this validation
            # but it's recommended to use it for security
            logger.warning("Telegram webhook signature verification skipped - no secret token")
            return True
            
        except Exception as e:
            logger.error("Telegram signature verification error", extra={
                "error": str(e),
                "source_ip": request.client.host if request.client else "unknown"
            })
            return False
    
    @staticmethod
    def get_client_ip(request: Request) -> str:
        """Get client IP for logging and security"""
        # Check for forwarded headers first (common in production)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
            
        # Fallback to client IP
        if request.client:
            return request.client.host
            
        return "unknown"