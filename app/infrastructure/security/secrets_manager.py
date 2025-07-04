import os
import json
import base64
import logging
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from cryptography.fernet import Fernet
from app.utils.secure_logging import SecureLogger

logger = logging.getLogger(__name__)

class SecretProvider(ABC):
    """Abstract base class for secret providers"""
    
    @abstractmethod
    async def get_secret(self, key: str) -> Optional[str]:
        pass
    
    @abstractmethod
    async def set_secret(self, key: str, value: str) -> bool:
        pass
    
    @abstractmethod
    async def delete_secret(self, key: str) -> bool:
        pass
    
    @abstractmethod
    async def list_secrets(self) -> list[str]:
        pass

class EnvironmentSecretProvider(SecretProvider):
    """Environment variable secret provider"""
    
    async def get_secret(self, key: str) -> Optional[str]:
        return os.getenv(key)
    
    async def set_secret(self, key: str, value: str) -> bool:
        os.environ[key] = value
        return True
    
    async def delete_secret(self, key: str) -> bool:
        if key in os.environ:
            del os.environ[key]
            return True
        return False
    
    async def list_secrets(self) -> list[str]:
        # Return only keys that look like secrets
        secret_patterns = ['TOKEN', 'KEY', 'SECRET', 'PASSWORD', 'API']
        return [
            key for key in os.environ.keys()
            if any(pattern in key.upper() for pattern in secret_patterns)
        ]

class FileSecretProvider(SecretProvider):
    """File-based encrypted secret provider"""
    
    def __init__(self, secrets_file: str = "/app/secrets/secrets.enc"):
        self.secrets_file = secrets_file
        self.encryption_key = self._get_or_create_encryption_key()
        self.fernet = Fernet(self.encryption_key)
        self.secrets_cache: Dict[str, str] = {}
        self.cache_timestamp = None
        self.cache_ttl = 300  # 5 minutes
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key"""
        key_file = "/app/secrets/key.enc"
        
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            # Create new key
            key = Fernet.generate_key()
            os.makedirs(os.path.dirname(key_file), exist_ok=True)
            with open(key_file, 'wb') as f:
                f.write(key)
            SecureLogger.safe_log_info(logger, "New encryption key created")
            return key
    
    def _load_secrets(self) -> Dict[str, str]:
        """Load and decrypt secrets from file"""
        if not os.path.exists(self.secrets_file):
            return {}
        
        try:
            with open(self.secrets_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self.fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to load secrets", e)
            return {}
    
    def _save_secrets(self, secrets: Dict[str, str]) -> bool:
        """Encrypt and save secrets to file"""
        try:
            os.makedirs(os.path.dirname(self.secrets_file), exist_ok=True)
            
            json_data = json.dumps(secrets).encode()
            encrypted_data = self.fernet.encrypt(json_data)
            
            with open(self.secrets_file, 'wb') as f:
                f.write(encrypted_data)
            
            # Update cache
            self.secrets_cache = secrets.copy()
            self.cache_timestamp = datetime.utcnow()
            
            return True
        
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to save secrets", e)
            return False
    
    def _get_cached_secrets(self) -> Optional[Dict[str, str]]:
        """Get secrets from cache if not expired"""
        if (self.cache_timestamp is None or 
            datetime.utcnow() - self.cache_timestamp > timedelta(seconds=self.cache_ttl)):
            return None
        
        return self.secrets_cache
    
    async def get_secret(self, key: str) -> Optional[str]:
        secrets = self._get_cached_secrets()
        if secrets is None:
            secrets = self._load_secrets()
            self.secrets_cache = secrets
            self.cache_timestamp = datetime.utcnow()
        
        return secrets.get(key)
    
    async def set_secret(self, key: str, value: str) -> bool:
        secrets = self._load_secrets()
        secrets[key] = value
        return self._save_secrets(secrets)
    
    async def delete_secret(self, key: str) -> bool:
        secrets = self._load_secrets()
        if key in secrets:
            del secrets[key]
            return self._save_secrets(secrets)
        return False
    
    async def list_secrets(self) -> list[str]:
        secrets = self._get_cached_secrets()
        if secrets is None:
            secrets = self._load_secrets()
        
        return list(secrets.keys())

class AWSSecretsManagerProvider(SecretProvider):
    """AWS Secrets Manager provider"""
    
    def __init__(self):
        try:
            import boto3
            self.client = boto3.client('secretsmanager')
        except ImportError:
            raise ImportError("boto3 required for AWS Secrets Manager")
    
    async def get_secret(self, key: str) -> Optional[str]:
        try:
            response = self.client.get_secret_value(SecretId=key)
            return response['SecretString']
        except Exception as e:
            SecureLogger.safe_log_error(logger, f"Failed to get secret from AWS: {key}", e)
            return None
    
    async def set_secret(self, key: str, value: str) -> bool:
        try:
            self.client.create_secret(Name=key, SecretString=value)
            return True
        except self.client.exceptions.ResourceExistsException:
            # Update existing secret
            try:
                self.client.update_secret(SecretId=key, SecretString=value)
                return True
            except Exception as e:
                SecureLogger.safe_log_error(logger, f"Failed to update secret in AWS: {key}", e)
                return False
        except Exception as e:
            SecureLogger.safe_log_error(logger, f"Failed to create secret in AWS: {key}", e)
            return False
    
    async def delete_secret(self, key: str) -> bool:
        try:
            self.client.delete_secret(SecretId=key, ForceDeleteWithoutRecovery=True)
            return True
        except Exception as e:
            SecureLogger.safe_log_error(logger, f"Failed to delete secret from AWS: {key}", e)
            return False
    
    async def list_secrets(self) -> list[str]:
        try:
            response = self.client.list_secrets()
            return [secret['Name'] for secret in response['SecretList']]
        except Exception as e:
            SecureLogger.safe_log_error(logger, "Failed to list secrets from AWS", e)
            return []

class SecretsManager:
    """Unified secrets management with multiple providers"""
    
    def __init__(self, primary_provider: SecretProvider, fallback_provider: Optional[SecretProvider] = None):
        self.primary_provider = primary_provider
        self.fallback_provider = fallback_provider or EnvironmentSecretProvider()
    
    async def get_secret(self, key: str, fallback_to_env: bool = True) -> Optional[str]:
        """Get secret with fallback support"""
        
        # Try primary provider first
        value = await self.primary_provider.get_secret(key)
        if value is not None:
            return value
        
        # Try fallback provider
        if fallback_to_env and self.fallback_provider:
            value = await self.fallback_provider.get_secret(key)
            if value is not None:
                SecureLogger.safe_log_warning(logger, f"Secret retrieved from fallback provider: {key}")
                return value
        
        SecureLogger.safe_log_warning(logger, f"Secret not found: {key}")
        return None
    
    async def set_secret(self, key: str, value: str) -> bool:
        """Set secret in primary provider"""
        success = await self.primary_provider.set_secret(key, value)
        
        if success:
            SecureLogger.safe_log_info(logger, f"Secret updated: {key}")
        else:
            SecureLogger.safe_log_error(logger, f"Failed to update secret: {key}", None)
        
        return success
    
    async def rotate_secret(self, key: str, new_value: str) -> bool:
        """Rotate secret with validation"""
        
        # Get current value for rollback
        old_value = await self.get_secret(key)
        
        # Set new value
        if not await self.set_secret(key, new_value):
            return False
        
        # Validate new secret works (implement validation logic based on secret type)
        if not await self._validate_secret(key, new_value):
            # Rollback
            if old_value:
                await self.set_secret(key, old_value)
            SecureLogger.safe_log_error(logger, f"Secret validation failed, rolled back: {key}", None)
            return False
        
        SecureLogger.safe_log_info(logger, f"Secret rotated successfully: {key}")
        return True
    
    async def _validate_secret(self, key: str, value: str) -> bool:
        """Validate secret value (override for specific validation logic)"""
        
        # Basic validation - check if value is not empty
        if not value or not value.strip():
            return False
        
        # Add specific validation logic for different types of secrets
        if 'API_KEY' in key.upper():
            return len(value) >= 20  # API keys should be at least 20 chars
        
        if 'TOKEN' in key.upper():
            return len(value) >= 32  # Tokens should be at least 32 chars
        
        if 'PASSWORD' in key.upper():
            return len(value) >= 8  # Passwords should be at least 8 chars
        
        return True
    
    async def get_all_secrets(self) -> Dict[str, str]:
        """Get all secrets (be careful with this)"""
        
        secrets = {}
        
        # Get from primary provider
        primary_keys = await self.primary_provider.list_secrets()
        for key in primary_keys:
            value = await self.primary_provider.get_secret(key)
            if value:
                secrets[key] = value
        
        # Get from fallback provider (if not already in primary)
        if self.fallback_provider:
            fallback_keys = await self.fallback_provider.list_secrets()
            for key in fallback_keys:
                if key not in secrets:
                    value = await self.fallback_provider.get_secret(key)
                    if value:
                        secrets[key] = value
        
        SecureLogger.safe_log_warning(logger, f"Retrieved all secrets: {len(secrets)} secrets")
        return secrets
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of secret providers"""
        
        health = {
            "primary_provider": "unknown",
            "fallback_provider": "unknown",
            "test_secret_accessible": False
        }
        
        # Test primary provider
        try:
            test_keys = await self.primary_provider.list_secrets()
            health["primary_provider"] = "healthy"
        except Exception as e:
            health["primary_provider"] = f"error: {str(e)}"
        
        # Test fallback provider
        if self.fallback_provider:
            try:
                test_keys = await self.fallback_provider.list_secrets()
                health["fallback_provider"] = "healthy"
            except Exception as e:
                health["fallback_provider"] = f"error: {str(e)}"
        
        # Test secret retrieval
        try:
            test_secret = await self.get_secret("WHATSAPP_TOKEN")
            health["test_secret_accessible"] = test_secret is not None
        except Exception:
            health["test_secret_accessible"] = False
        
        return health

# Create global secrets manager
def create_secrets_manager() -> SecretsManager:
    """Create secrets manager based on environment"""
    
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "production":
        # Use AWS Secrets Manager in production
        try:
            primary_provider = AWSSecretsManagerProvider()
            SecureLogger.safe_log_info(logger, "Using AWS Secrets Manager")
        except ImportError:
            # Fallback to file-based secrets
            primary_provider = FileSecretProvider()
            SecureLogger.safe_log_warning(logger, "AWS not available, using file-based secrets")
    else:
        # Use file-based secrets in development
        primary_provider = FileSecretProvider()
        SecureLogger.safe_log_info(logger, "Using file-based secrets")
    
    return SecretsManager(
        primary_provider=primary_provider,
        fallback_provider=EnvironmentSecretProvider()
    )

# Global secrets manager instance
secrets_manager = create_secrets_manager()