from fastapi import Request, Response
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class SecurityFilterMiddleware:
    """Filter out suspicious requests during development"""
    
    def __init__(self, app):
        self.app = app
        
        # Common suspicious patterns
        self.suspicious_patterns = [
            'jndi:',
            'ldap:',
            'cgi-bin',
            '.env',
            '.git',
            'admin',
            'phpmyadmin',
            'wp-admin',
            'undefined',
            'null'
        ]
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            path = request.url.path.lower()
            query = str(request.url.query).lower()
            
            # Check for suspicious patterns
            if any(pattern in path or pattern in query for pattern in self.suspicious_patterns):
                logger.warning("Blocked suspicious request", extra={
                    "path": request.url.path,
                    "query": str(request.url.query),
                    "method": request.method,
                    "client_ip": request.client.host if request.client else "unknown"
                })
                
                # Return 444 (connection closed without response) for suspicious requests
                response = Response(status_code=444)
                await response(scope, receive, send)
                return
        
        # Continue with normal processing
        await self.app(scope, receive, send)