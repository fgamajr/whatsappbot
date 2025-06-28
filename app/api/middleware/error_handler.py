from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import json
from app.core.exceptions import InterviewBotException

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        
        except InterviewBotException as e:
            logger.error("Application error", extra={
                "error_type": type(e).__name__,
                "error_code": e.error_code,
                "message": e.message,
                "path": str(request.url)
            })
            
            return Response(
                content=json.dumps({
                    "error": e.message,
                    "error_code": e.error_code
                }),
                status_code=400,
                media_type="application/json"
            )
        
        except Exception as e:
            logger.error("Unexpected error", extra={
                "error": str(e),
                "path": str(request.url)
            })
            
            return Response(
                content=json.dumps({
                    "error": "Internal server error"
                }),
                status_code=500,
                media_type="application/json"
            )
