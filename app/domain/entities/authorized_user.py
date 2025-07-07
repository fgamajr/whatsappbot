from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    LIMITED = "limited"


class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


class Platform(str, Enum):
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"


class UsageStats(BaseModel):
    """Track user usage statistics"""
    daily_count: int = 0
    monthly_count: int = 0
    last_reset_date: datetime = Field(default_factory=datetime.now)
    total_messages: int = 0
    
    def reset_daily_if_needed(self):
        """Reset daily count if new day"""
        today = datetime.now().date()
        if self.last_reset_date.date() < today:
            self.daily_count = 0
            self.last_reset_date = datetime.now()
    
    def reset_monthly_if_needed(self):
        """Reset monthly count if new month"""
        now = datetime.now()
        if (self.last_reset_date.year < now.year or 
            self.last_reset_date.month < now.month):
            self.monthly_count = 0


class AuthorizedUser(BaseModel):
    """Represents an authorized user with platform-specific identification"""
    
    # Platform-specific identifier (phone number for WhatsApp, chat_id for Telegram)
    platform_identifier: str
    platform: Platform
    
    # User information
    display_name: str
    role: UserRole = UserRole.USER
    status: UserStatus = UserStatus.ACTIVE
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    
    # Usage limits and tracking
    daily_limit: int = 50  # Max messages per day
    monthly_limit: int = 1000  # Max messages per month
    usage_stats: UsageStats = Field(default_factory=UsageStats)
    
    # Permissions
    allowed_features: List[str] = Field(default_factory=lambda: ["audio_analysis", "text_commands"])
    
    # Notes for admin reference
    notes: Optional[str] = None
    
    @property
    def unified_id(self) -> str:
        """Generate platform-specific unified ID"""
        prefix = "wa" if self.platform == Platform.WHATSAPP else "tg"
        return f"{prefix}:{self.platform_identifier}"
    
    def is_active(self) -> bool:
        """Check if user is active and not expired"""
        if self.status != UserStatus.ACTIVE:
            return False
        
        if self.expires_at and datetime.now() > self.expires_at:
            return False
            
        return True
    
    def can_send_message(self) -> bool:
        """Check if user can send a message based on limits"""
        if not self.is_active():
            return False
        
        # Reset counters if needed
        self.usage_stats.reset_daily_if_needed()
        self.usage_stats.reset_monthly_if_needed()
        
        # Check limits
        if self.usage_stats.daily_count >= self.daily_limit:
            return False
        
        if self.usage_stats.monthly_count >= self.monthly_limit:
            return False
            
        return True
    
    def record_message_usage(self):
        """Record a message usage"""
        self.usage_stats.reset_daily_if_needed()
        self.usage_stats.reset_monthly_if_needed()
        
        self.usage_stats.daily_count += 1
        self.usage_stats.monthly_count += 1
        self.usage_stats.total_messages += 1
        self.last_used_at = datetime.now()
        self.updated_at = datetime.now()
    
    def has_feature_permission(self, feature: str) -> bool:
        """Check if user has permission for specific feature"""
        if self.role == UserRole.ADMIN:
            return True
        return feature in self.allowed_features
    
    def suspend(self, reason: Optional[str] = None):
        """Suspend user access"""
        self.status = UserStatus.SUSPENDED
        self.updated_at = datetime.now()
        if reason and self.notes:
            self.notes += f"\nSuspended: {reason}"
        elif reason:
            self.notes = f"Suspended: {reason}"
    
    def activate(self):
        """Activate user access"""
        self.status = UserStatus.ACTIVE
        self.updated_at = datetime.now()
    
    def set_expiration(self, days: int):
        """Set user expiration date"""
        self.expires_at = datetime.now() + timedelta(days=days)
        self.updated_at = datetime.now()