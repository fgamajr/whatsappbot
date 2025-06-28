from fastapi import APIRouter
from typing import Dict
import logging
from app.infrastructure.database.mongodb import MongoDB
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/live")
async def liveness():
    """Liveness probe"""
    return {"status": "alive", "service": "interview-bot"}


@router.get("/ready")
async def readiness():
    """Readiness probe with dependencies check"""
    health_status = {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "services": {}
    }
    
    # Check MongoDB
    try:
        db = await MongoDB.get_database()
        await db.command("ping")
        health_status["services"]["mongodb"] = "connected"
    except Exception as e:
        health_status["services"]["mongodb"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check AI services configuration
    health_status["services"]["openai"] = "configured" if settings.OPENAI_API_KEY else "missing_key"
    health_status["services"]["gemini"] = "configured" if settings.GEMINI_API_KEY else "missing_key"
    health_status["services"]["whatsapp"] = "configured" if settings.WHATSAPP_TOKEN else "missing_token"
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    return health_status
