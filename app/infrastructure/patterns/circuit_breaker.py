import asyncio
import time
import logging
from typing import Callable, Any, Optional, Dict
from enum import Enum
from dataclasses import dataclass
from functools import wraps
from app.utils.secure_logging import SecureLogger

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit breaker triggered, rejecting calls
    HALF_OPEN = "half_open"  # Testing if service recovered

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5          # Number of failures before opening
    recovery_timeout: int = 60          # Seconds before attempting recovery
    expected_exception: type = Exception  # Exception type to count as failure
    timeout: float = 30.0               # Operation timeout in seconds

class CircuitBreakerOpenException(Exception):
    """Raised when circuit breaker is open"""
    pass

class CircuitBreaker:
    """Circuit breaker implementation for external service calls"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.success_count = 0  # For half-open state
        self._lock = asyncio.Lock()
    
    async def __aenter__(self):
        await self._check_state()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self._on_success()
        elif issubclass(exc_type, self.config.expected_exception):
            await self._on_failure()
        # Let other exceptions propagate
        return False
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        async with self:
            # Add timeout protection
            try:
                result = await asyncio.wait_for(
                    func(*args, **kwargs), 
                    timeout=self.config.timeout
                )
                return result
            except asyncio.TimeoutError as e:
                SecureLogger.safe_log_warning(logger, f"Circuit breaker timeout", {
                    'circuit_name': self.name,
                    'timeout': self.config.timeout
                })
                raise self.config.expected_exception(f"Timeout after {self.config.timeout}s") from e
    
    async def _check_state(self):
        """Check and potentially update circuit breaker state"""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    SecureLogger.safe_log_info(logger, "Circuit breaker half-open", {
                        'circuit_name': self.name
                    })
                else:
                    raise CircuitBreakerOpenException(
                        f"Circuit breaker '{self.name}' is open"
                    )
    
    async def _on_success(self):
        """Handle successful operation"""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= 3:  # Require 3 successes to close
                    self._reset()
                    SecureLogger.safe_log_info(logger, "Circuit breaker closed", {
                        'circuit_name': self.name,
                        'success_count': self.success_count
                    })
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0  # Reset failure count on success
    
    async def _on_failure(self):
        """Handle failed operation"""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # If we fail in half-open, go back to open
                self.state = CircuitState.OPEN
                SecureLogger.safe_log_warning(logger, "Circuit breaker re-opened", {
                    'circuit_name': self.name,
                    'failure_count': self.failure_count
                })
            elif (self.state == CircuitState.CLOSED and 
                  self.failure_count >= self.config.failure_threshold):
                # Open the circuit breaker
                self.state = CircuitState.OPEN
                SecureLogger.safe_log_error(logger, "Circuit breaker opened", None, {
                    'circuit_name': self.name,
                    'failure_count': self.failure_count,
                    'threshold': self.config.failure_threshold
                })
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        
        return (time.time() - self.last_failure_time) >= self.config.recovery_timeout
    
    def _reset(self):
        """Reset circuit breaker to closed state"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
    
    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status"""
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'last_failure_time': self.last_failure_time,
            'config': {
                'failure_threshold': self.config.failure_threshold,
                'recovery_timeout': self.config.recovery_timeout,
                'timeout': self.config.timeout
            }
        }

class CircuitBreakerManager:
    """Manages multiple circuit breakers"""
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
    
    def get_breaker(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Get or create circuit breaker"""
        if name not in self.breakers:
            if config is None:
                config = CircuitBreakerConfig()
            self.breakers[name] = CircuitBreaker(name, config)
        
        return self.breakers[name]
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers"""
        return {name: breaker.get_status() for name, breaker in self.breakers.items()}

# Global circuit breaker manager
circuit_breaker_manager = CircuitBreakerManager()

# Decorator for easy use
def circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None):
    """Decorator to add circuit breaker to async functions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            breaker = circuit_breaker_manager.get_breaker(name, config)
            return await breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator

# Predefined circuit breakers for common services
def get_openai_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for OpenAI API"""
    config = CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=30,
        timeout=60.0,
        expected_exception=Exception
    )
    return circuit_breaker_manager.get_breaker("openai", config)

def get_gemini_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for Gemini API"""
    config = CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=30,
        timeout=90.0,
        expected_exception=Exception
    )
    return circuit_breaker_manager.get_breaker("gemini", config)

def get_whatsapp_circuit_breaker() -> CircuitBreaker:
    """Get circuit breaker for WhatsApp API"""
    config = CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60,
        timeout=30.0,
        expected_exception=Exception
    )
    return circuit_breaker_manager.get_breaker("whatsapp", config)