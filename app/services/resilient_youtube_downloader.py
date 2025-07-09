"""
Resilient YouTube downloader that communicates with yt-dlp service
This provides fallback mechanisms and automatic updates
"""

import asyncio
import base64
import logging
import httpx
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta

from app.core.config import settings
from app.utils.youtube_detector import YouTubeURLDetector
from app.services.youtube_downloader import YouTubeDownloadError

logger = logging.getLogger(__name__)

class ResilientYouTubeService:
    """
    Resilient YouTube downloader with automatic fallbacks and updates
    """
    
    def __init__(self):
        self.service_url = getattr(settings, 'YTDLP_SERVICE_URL', 'http://localhost:8080')
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        self.last_update_check = None
        self.update_interval = timedelta(hours=6)  # Check for updates every 6 hours
        
    async def _check_service_health(self) -> bool:
        """Check if yt-dlp service is healthy"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.service_url}/health")
                return response.status_code == 200
        except Exception as e:
            logger.error("Service health check failed", extra={"error": str(e)})
            return False
    
    async def _update_service(self) -> bool:
        """Update yt-dlp service to latest version"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{self.service_url}/update")
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info("Service update completed", extra={
                        "success": result.get("success"),
                        "old_version": result.get("old_version"),
                        "new_version": result.get("new_version"),
                        "message": result.get("message")
                    })
                    return result.get("success", False)
                else:
                    logger.error("Service update failed", extra={
                        "status_code": response.status_code,
                        "response": response.text
                    })
                    return False
                    
        except Exception as e:
            logger.error("Service update error", extra={"error": str(e)})
            return False
    
    async def _should_update(self) -> bool:
        """Check if we should update the service"""
        if self.last_update_check is None:
            return True
            
        return datetime.now() - self.last_update_check > self.update_interval
    
    async def _download_with_retry(self, url: str, progress_callback: Optional[callable] = None) -> Tuple[bytes, Dict[str, Any]]:
        """Download with retry logic and automatic updates"""
        
        # Check if we should update
        if await self._should_update():
            logger.info("Checking for yt-dlp updates...")
            update_success = await self._update_service()
            self.last_update_check = datetime.now()
            
            if update_success:
                logger.info("yt-dlp service updated successfully")
            else:
                logger.warning("yt-dlp service update failed, continuing with current version")
        
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # Check service health
                if not await self._check_service_health():
                    logger.warning(f"Service unhealthy on attempt {attempt + 1}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self.retry_delay)
                        continue
                    else:
                        raise YouTubeDownloadError("yt-dlp service is not available")
                
                # Prepare request
                request_data = {
                    "url": url,
                    "max_file_size": settings.YOUTUBE_MAX_FILE_SIZE,
                    "max_duration": settings.YOUTUBE_MAX_DURATION,
                    "quality": settings.YOUTUBE_QUALITY
                }
                
                # Make request
                async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minute timeout
                    response = await client.post(
                        f"{self.service_url}/download",
                        json=request_data
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        
                        if result.get("success"):
                            # Decode base64 data
                            file_data = base64.b64decode(result["file_data"])
                            metadata = result["metadata"]
                            
                            logger.info("Download successful via service", extra={
                                "url": url,
                                "file_size": len(file_data),
                                "title": metadata.get("title")
                            })
                            
                            return file_data, metadata
                        else:
                            # Service returned error
                            error_msg = result.get("error", "Unknown error")
                            logger.error("Service returned error", extra={
                                "url": url,
                                "error": error_msg
                            })
                            
                            # Check if it's a temporary error worth retrying
                            if "network" in error_msg.lower() or "connection" in error_msg.lower():
                                last_error = YouTubeDownloadError(error_msg)
                                if attempt < self.max_retries - 1:
                                    await asyncio.sleep(self.retry_delay)
                                    continue
                            
                            raise YouTubeDownloadError(error_msg)
                    else:
                        logger.error("Service HTTP error", extra={
                            "status_code": response.status_code,
                            "response": response.text
                        })
                        last_error = YouTubeDownloadError(f"Service error: {response.status_code}")
                        
            except httpx.TimeoutException:
                logger.error("Service timeout", extra={"attempt": attempt + 1})
                last_error = YouTubeDownloadError("Service timeout")
                
            except httpx.ConnectError:
                logger.error("Service connection error", extra={"attempt": attempt + 1})
                last_error = YouTubeDownloadError("Cannot connect to yt-dlp service")
                
            except YouTubeDownloadError:
                raise
                
            except Exception as e:
                logger.error("Unexpected error", extra={
                    "error": str(e),
                    "attempt": attempt + 1
                })
                last_error = YouTubeDownloadError(f"Unexpected error: {str(e)}")
            
            # Wait before retry
            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
        
        # All retries failed
        if last_error:
            raise last_error
        else:
            raise YouTubeDownloadError("All download attempts failed")
    
    async def download_video(self, url: str, progress_callback: Optional[callable] = None) -> Tuple[bytes, Dict[str, Any]]:
        """
        Download YouTube video with resilience features
        """
        try:
            # Validate URL
            if not YouTubeURLDetector.is_youtube_url(url):
                raise YouTubeDownloadError("URL não é um link válido do YouTube")
            
            # Normalize URL
            normalized_url = YouTubeURLDetector.normalize_youtube_url(url)
            if not normalized_url:
                raise YouTubeDownloadError("Não foi possível processar o link do YouTube")
            
            logger.info("Starting resilient YouTube download", extra={
                "url": normalized_url,
                "original_url": url
            })
            
            # Download with retry logic
            return await self._download_with_retry(normalized_url, progress_callback)
            
        except YouTubeDownloadError:
            raise
        except Exception as e:
            logger.error("Unexpected error in resilient download", extra={
                "error": str(e),
                "url": url
            })
            raise YouTubeDownloadError(f"Erro inesperado: {str(e)}")
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

# Global resilient service instance
resilient_youtube_service = ResilientYouTubeService()