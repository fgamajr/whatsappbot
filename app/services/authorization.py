from typing import Optional, Tuple
import logging
from app.domain.entities.authorized_user import AuthorizedUser, Platform
from app.infrastructure.database.repositories.authorized_user import AuthorizedUserRepository

logger = logging.getLogger(__name__)


class AuthorizationService:
    """Service for handling user authorization and access control"""
    
    def __init__(self):
        self.user_repo = AuthorizedUserRepository()
    
    def _get_platform_from_provider(self, provider: str) -> Optional[Platform]:
        """Convert provider string to Platform enum"""
        if provider == "whatsapp":
            return Platform.WHATSAPP
        elif provider == "telegram":
            return Platform.TELEGRAM
        else:
            logger.warning("Unknown provider", extra={"provider": provider})
            return None
    
    async def check_user_authorization(
        self, 
        provider: str, 
        user_identifier: str
    ) -> Tuple[bool, Optional[AuthorizedUser], str]:
        """
        Check if user is authorized to use the bot
        
        Returns:
            (is_authorized, user_object, reason)
        """
        try:
            platform = self._get_platform_from_provider(provider)
            if not platform:
                return False, None, f"Unsupported platform: {provider}"
            
            # Get user from database
            user = await self.user_repo.get_user(platform, user_identifier)
            
            if not user:
                logger.info("Unauthorized access attempt", extra={
                    "platform": platform,
                    "identifier": user_identifier
                })
                return False, None, "User not authorized"
            
            # Check if user is active
            if not user.is_active():
                status_reason = "expired" if user.expires_at else "suspended"
                logger.info("Inactive user access attempt", extra={
                    "platform": platform,
                    "identifier": user_identifier,
                    "status": user.status,
                    "reason": status_reason
                })
                return False, user, f"User account is {status_reason}"
            
            # Check usage limits
            if not user.can_send_message():
                logger.info("User exceeded limits", extra={
                    "platform": platform,
                    "identifier": user_identifier,
                    "daily_count": user.usage_stats.daily_count,
                    "daily_limit": user.daily_limit,
                    "monthly_count": user.usage_stats.monthly_count,
                    "monthly_limit": user.monthly_limit
                })
                return False, user, "Usage limit exceeded"
            
            # User is authorized
            logger.info("User authorized", extra={
                "platform": platform,
                "identifier": user_identifier,
                "display_name": user.display_name,
                "role": user.role
            })
            
            return True, user, "Authorized"
            
        except Exception as e:
            logger.error("Authorization check failed", extra={
                "error": str(e),
                "provider": provider,
                "identifier": user_identifier
            })
            return False, None, "Authorization system error"
    
    async def record_message_usage(self, provider: str, user_identifier: str) -> bool:
        """Record message usage for a user"""
        try:
            platform = self._get_platform_from_provider(provider)
            if not platform:
                return False
            
            return await self.user_repo.update_usage(platform, user_identifier)
            
        except Exception as e:
            logger.error("Failed to record usage", extra={
                "error": str(e),
                "provider": provider,
                "identifier": user_identifier
            })
            return False
    
    async def check_feature_permission(
        self, 
        provider: str, 
        user_identifier: str, 
        feature: str
    ) -> bool:
        """Check if user has permission for specific feature"""
        try:
            platform = self._get_platform_from_provider(provider)
            if not platform:
                return False
            
            user = await self.user_repo.get_user(platform, user_identifier)
            if not user or not user.is_active():
                return False
            
            return user.has_feature_permission(feature)
            
        except Exception as e:
            logger.error("Feature permission check failed", extra={
                "error": str(e),
                "provider": provider,
                "identifier": user_identifier,
                "feature": feature
            })
            return False
    
    async def get_user_info(self, provider: str, user_identifier: str) -> Optional[dict]:
        """Get user information for display purposes"""
        try:
            platform = self._get_platform_from_provider(provider)
            if not platform:
                return None
            
            user = await self.user_repo.get_user(platform, user_identifier)
            if not user:
                return None
            
            return {
                "unified_id": user.unified_id,
                "display_name": user.display_name,
                "role": user.role,
                "status": user.status,
                "daily_usage": user.usage_stats.daily_count,
                "daily_limit": user.daily_limit,
                "monthly_usage": user.usage_stats.monthly_count,
                "monthly_limit": user.monthly_limit,
                "allowed_features": user.allowed_features,
                "last_used": user.last_used_at
            }
            
        except Exception as e:
            logger.error("Failed to get user info", extra={
                "error": str(e),
                "provider": provider,
                "identifier": user_identifier
            })
            return None
    
    async def get_platform_stats(self) -> dict:
        """Get usage statistics by platform"""
        try:
            return await self.user_repo.get_usage_stats()
        except Exception as e:
            logger.error("Failed to get platform stats", extra={"error": str(e)})
            return {}


# Global authorization service instance
authorization_service = AuthorizationService()