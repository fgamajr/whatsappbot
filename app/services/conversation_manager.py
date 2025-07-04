import json
import logging
from typing import Optional, Dict, Any
from app.infrastructure.redis_client import get_redis_client

logger = logging.getLogger(__name__)

class ConversationManager:
    def __init__(self):
        self.redis = get_redis_client()
        self.prefix = "session:"
        self.ttl = 3600  # 1 hour

    def _get_key(self, user_id: str) -> str:
        return f"{self.prefix}{user_id}"

    def set_state(self, user_id: str, state: str, data: Optional[Dict[str, Any]] = None):
        """Sets the state for a user's conversation."""
        try:
            key = self._get_key(user_id)
            value = {"state": state, "data": data or {}}
            self.redis.set(key, json.dumps(value), ex=self.ttl)
            logger.info(f"State set for user {user_id}: {state}")
        except Exception as e:
            logger.error(f"Failed to set state for user {user_id}: {e}", exc_info=True)

    def get_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Gets the state for a user's conversation."""
        try:
            key = self._get_key(user_id)
            value = self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Failed to get state for user {user_id}: {e}", exc_info=True)
            return None

    def clear_state(self, user_id: str):
        """Clears the state for a user's conversation."""
        try:
            key = self._get_key(user_id)
            self.redis.delete(key)
            logger.info(f"State cleared for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to clear state for user {user_id}: {e}", exc_info=True)
