from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from app.api.v1 import webhooks, health
from app.api.middleware.error_handler import ErrorHandlerMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.infrastructure.database.mongodb import MongoDB

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
    
    yield
    
    # Shutdown
    await MongoDB.disconnect()
    logger.info("Interview Bot shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="WhatsApp Interview Bot with Clean Architecture",
    lifespan=lifespan
)

# Middleware
app.add_middleware(ErrorHandlerMiddleware)

# Routes
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(webhooks.router, prefix="/webhook", tags=["whatsapp"])


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
