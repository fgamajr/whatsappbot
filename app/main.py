from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from app.api.v1 import webhooks, health, messaging
from app.api.middleware.error_handler import ErrorHandlerMiddleware
from app.api.middleware.redis_rate_limiter import RedisRateLimiterMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.infrastructure.database.mongodb import MongoDB
from app.infrastructure.redis_client import redis_client
from app.celery_app import celery_app
from app.infrastructure.prometheus_metrics import prometheus_metrics
from app.infrastructure.metrics_collector import metrics_collector
from app.infrastructure.auto_scaler import auto_scaler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging(debug=settings.DEBUG)
    logger.info("Starting Interview Bot", extra={
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    })
    
    await MongoDB.connect()
    await redis_client.connect()
    
    # Verify Celery connection
    try:
        # Test Celery broker connection
        celery_app.control.inspect().stats()
        logger.info("Celery broker connection verified")
    except Exception as e:
        logger.warning(f"Celery broker connection failed: {e}")
    
    # Start monitoring services
    try:
        # Start Prometheus metrics server
        prometheus_metrics.start_metrics_server(8001)
        
        # Start metrics collector
        import asyncio
        asyncio.create_task(metrics_collector.start_collection())
        
        # Start auto-scaler
        asyncio.create_task(auto_scaler.start_auto_scaling())
        
        # Initialize circuit breakers for external services
        from app.infrastructure.patterns.circuit_breaker import (
            get_openai_circuit_breaker, get_gemini_circuit_breaker, get_whatsapp_circuit_breaker
        )
        get_openai_circuit_breaker()
        get_gemini_circuit_breaker() 
        get_whatsapp_circuit_breaker()
        
        # Initialize secrets manager
        from app.infrastructure.security.secrets_manager import secrets_manager
        secrets_health = await secrets_manager.health_check()
        logger.info(f"Secrets manager initialized: {secrets_health}")
        
        # Initialize business metrics collection
        from app.infrastructure.monitoring.business_metrics import business_metrics
        await business_metrics.record_metric("system_startup", 1.0, {"component": "main"})
        
        logger.info("All monitoring and security services started successfully")
    except Exception as e:
        logger.warning(f"Failed to start services: {e}")
    
    yield
    
    # Shutdown
    metrics_collector.stop_collection()
    auto_scaler.stop_auto_scaling()
    await MongoDB.disconnect()
    await redis_client.disconnect()
    logger.info("Interview Bot shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="WhatsApp Interview Bot with Clean Architecture",
    lifespan=lifespan
)

# Middleware
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(RedisRateLimiterMiddleware)

# Routes
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(webhooks.router, prefix="/webhook", tags=["whatsapp"])  # Legacy WhatsApp endpoint
app.include_router(messaging.router, prefix="/webhook", tags=["messaging"])  # New multi-provider endpoints

# Celery test endpoints (only in development)
if settings.DEBUG:
    from app.api.v1 import celery_test
    app.include_router(celery_test.router, prefix="/celery", tags=["celery"])

# Monitoring endpoints
from app.api.endpoints import monitoring
app.include_router(monitoring.router, tags=["monitoring"])

# Export endpoints
from app.api.endpoints import export
app.include_router(export.router, tags=["export"])


# Recovery routes
try:
    from app.api.v1.recovery import router as recovery_router
    app.include_router(recovery_router, prefix="", tags=["recovery"])
    logger.info("Recovery endpoints enabled")
except ImportError as e:
    logger.warning("Recovery endpoints not available", extra={"error": str(e)})


@app.get("/")
async def root():
    return {
        "message": f"{settings.APP_NAME} is running!",
        "version": settings.VERSION,
        "status": "healthy",
        "features": [
            "Clean Architecture",
            "Background Processing",
            "MongoDB Atlas",
            "Whisper + Gemini",
            "Production Ready"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
