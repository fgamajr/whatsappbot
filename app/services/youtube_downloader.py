import asyncio
import io
import tempfile
import os
from typing import Optional, Tuple, Dict, Any
import logging
from datetime import datetime, timedelta
import yt_dlp
import ffmpeg
from pathlib import Path

from app.core.config import settings
from app.utils.youtube_detector import YouTubeURLDetector
from app.core.logging import setup_youtube_logging


logger = logging.getLogger(__name__)


class YouTubeDownloadError(Exception):
    """Custom exception for YouTube download errors"""
    pass


class YouTubeDownloadService:
    """Service for downloading YouTube videos with comprehensive error handling"""
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.timeout = settings.YOUTUBE_DOWNLOAD_TIMEOUT
        self.max_duration = settings.YOUTUBE_MAX_DURATION
        self.max_file_size = settings.YOUTUBE_MAX_FILE_SIZE
        self.quality = settings.YOUTUBE_QUALITY
        
        # Initialize YouTube-specific logging
        setup_youtube_logging()
    
    async def download_video(self, url: str, progress_callback: Optional[callable] = None) -> Tuple[bytes, Dict[str, Any]]:
        """
        Download YouTube video and return as bytes with metadata
        
        Args:
            url: YouTube URL
            progress_callback: Optional callback for progress updates
            
        Returns:
            Tuple of (video_bytes, metadata_dict)
            
        Raises:
            YouTubeDownloadError: If download fails for any reason
        """
        try:
            # Validate URL first
            if not YouTubeURLDetector.is_youtube_url(url):
                raise YouTubeDownloadError("URL não é um link válido do YouTube")
            
            # Normalize URL
            normalized_url = YouTubeURLDetector.normalize_youtube_url(url)
            if not normalized_url:
                raise YouTubeDownloadError("Não foi possível processar o link do YouTube")
            
            logger.info("Starting YouTube download", extra={
                "url": normalized_url,
                "original_url": url
            })
            
            # Get video info first to validate
            info = await self._get_video_info(normalized_url)
            
            # Validate video constraints
            self._validate_video_constraints(info)
            
            # Download video
            video_data, final_info = await self._download_video_data(normalized_url, info, progress_callback)
            
            logger.info("YouTube download completed", extra={
                "video_id": info.get('id'),
                "title": info.get('title', 'Unknown'),
                "duration": info.get('duration'),
                "file_size": len(video_data)
            })
            
            return video_data, final_info
            
        except YouTubeDownloadError:
            raise
        except asyncio.TimeoutError:
            raise YouTubeDownloadError("Timeout: Download demorou mais que 5 minutos")
        except Exception as e:
            logger.error("Unexpected error in YouTube download", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "url": url,
                "traceback": True
            }, exc_info=True)
            raise YouTubeDownloadError(f"Erro inesperado: {str(e)}")
    
    async def _get_video_info(self, url: str) -> Dict[str, Any]:
        """Get video information without downloading"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,
                'socket_timeout': 30,
            }
            
            def _extract_info():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            info = await asyncio.wait_for(
                loop.run_in_executor(None, _extract_info),
                timeout=60
            )
            
            if not info:
                raise YouTubeDownloadError("Não foi possível obter informações do vídeo")
            
            return info
            
        except asyncio.TimeoutError:
            raise YouTubeDownloadError("Timeout ao obter informações do vídeo")
        except yt_dlp.DownloadError as e:
            error_msg = str(e).lower()
            if 'private' in error_msg:
                raise YouTubeDownloadError("❌ Vídeo privado ou não disponível")
            elif 'not available' in error_msg:
                raise YouTubeDownloadError("❌ Vídeo não disponível na sua região")
            elif 'removed' in error_msg or 'deleted' in error_msg:
                raise YouTubeDownloadError("❌ Vídeo foi removido ou deletado")
            elif 'age' in error_msg and 'restrict' in error_msg:
                raise YouTubeDownloadError("❌ Vídeo com restrição de idade")
            else:
                raise YouTubeDownloadError(f"❌ Erro ao acessar vídeo: {str(e)}")
        except Exception as e:
            logger.error("Error getting video info", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "url": url
            })
            raise YouTubeDownloadError(f"❌ Erro ao obter informações do vídeo: {str(e)}")
    
    def _validate_video_constraints(self, info: Dict[str, Any]) -> None:
        """Validate video meets our constraints"""
        try:
            # Log size estimates but don't fail early - let format selection handle it
            filesize_approx = info.get('filesize') or info.get('filesize_approx')
            if filesize_approx:
                size_mb = filesize_approx / (1024 * 1024)
                max_mb = self.max_file_size / (1024 * 1024)
                logger.info("Video size estimate available", extra={
                    "estimated_size_mb": size_mb,
                    "max_size_mb": max_mb,
                    "video_id": info.get('id'),
                    "will_try_smaller_formats": size_mb > max_mb
                })

            # Check duration
            duration = info.get('duration')
            if duration and duration > self.max_duration:
                hours = duration // 3600
                minutes = (duration % 3600) // 60
                max_hours = self.max_duration // 3600
                max_minutes = (self.max_duration % 3600) // 60
                raise YouTubeDownloadError(
                    f"❌ Vídeo muito longo: {hours}h{minutes}m\n"
                    f"Limite máximo: {max_hours}h{max_minutes}m"
                )
            
            # Check if video is available
            if info.get('availability') in ['private', 'premium_only', 'subscriber_only']:
                raise YouTubeDownloadError("❌ Vídeo não está disponível publicamente")
            
            # Check if live stream
            if info.get('is_live'):
                raise YouTubeDownloadError("❌ Não é possível processar transmissões ao vivo")
            
            # Check if age restricted without login
            if info.get('age_limit', 0) > 0:
                raise YouTubeDownloadError("❌ Vídeo com restrição de idade")
            
            logger.info("Video validation passed", extra={
                "video_id": info.get('id'),
                "title": info.get('title'),
                "duration": duration,
                "availability": info.get('availability')
            })
            
        except YouTubeDownloadError:
            raise
        except Exception as e:
            logger.error("Error validating video constraints", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "video_info": info
            })
            raise YouTubeDownloadError(f"❌ Erro ao validar vídeo: {str(e)}")
    
    async def _download_video_data(self, url: str, info: Dict[str, Any], progress_callback: Optional[callable] = None) -> Tuple[bytes, Dict[str, Any]]:
        """Download video data to memory with better error handling"""
        # Add more specific error catching
        try:
            result = await self._download_with_format_string(url, info, self.quality, progress_callback)
            logger.info("Download successful", extra={
                "url": url,
                "file_size": len(result[0]) if result else 0
            })
            return result
        except YouTubeDownloadError as e:
            error_msg = str(e).lower()
            logger.error("Download error details", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "url": url,
                "primary_format": self.quality
            })
            
            if "nenhum formato disponível" in error_msg or "requested format is not available" in error_msg:
                logger.info("Primary format failed, trying exhaustive format list")
                return await self._download_with_exhaustive_formats(url, info, progress_callback)
            else:
                raise
        except Exception as e:
            # Log the full traceback
            import traceback
            logger.error("Unexpected download error", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "url": url,
                "traceback": traceback.format_exc()
            })
            raise YouTubeDownloadError(f"Download failed: {str(e)}")

    
    async def _download_with_format_string(self, url: str, info: Dict[str, Any], format_string: str, progress_callback: Optional[callable] = None) -> Tuple[bytes, Dict[str, Any]]:
        """Download using a format string with built-in fallbacks"""
        import uuid
        
        # Create unique temporary file path to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        video_id = info.get('id', 'unknown')
        temp_filename = f"yt_download_{video_id}_{unique_id}"
        temp_path = os.path.join(self.temp_dir, temp_filename)
        
        def _download_sync():
            """Synchronous download function with better options"""
            
            # Progress hook for yt-dlp
            def ydl_progress_hook(d):
                if d['status'] == 'downloading' and progress_callback:
                    asyncio.run(progress_callback(d))

            # Use a simple, reliable format string
            simple_format = (
                "best[ext=mp4][height<=720]/best[ext=mp4]/best[height<=720]/best"
            )
            
            ydl_opts = {
                'format': simple_format,
                'outtmpl': temp_path + '.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 30,
                'retries': 3,
                'fragment_retries': 3,
                'max_filesize': self.max_file_size,
                'overwrites': True,
                'nocheckcertificate': True,
                'prefer_insecure': True,
                'progress_hooks': [ydl_progress_hook],
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            # Find the actual downloaded file
            downloaded_files = [f for f in os.listdir(self.temp_dir) if f.startswith(temp_filename)]
            
            if not downloaded_files:
                raise YouTubeDownloadError("Download completed but no file found")
                
            actual_file = os.path.join(self.temp_dir, downloaded_files[0])
            
            if os.path.getsize(actual_file) == 0:
                raise YouTubeDownloadError("Downloaded file is empty")
                
            return actual_file
        
        try:
            logger.info("Starting download with format string", extra={
                "url": url,
                "format": format_string,
                "temp_path": temp_path
            })
            
            # Run download in executor
            loop = asyncio.get_event_loop()
            actual_file = await asyncio.wait_for(
                loop.run_in_executor(None, _download_sync),
                timeout=self.timeout
            )
            
            # Validate file
            file_size = os.path.getsize(actual_file)
            logger.info("Download completed", extra={
                "actual_file": actual_file,
                "file_size": file_size,
                "file_size_mb": file_size / (1024 * 1024),
                "format_used": format_string
            })
            
            if file_size > self.max_file_size:
                size_mb = file_size / (1024 * 1024)
                max_mb = self.max_file_size / (1024 * 1024)
                raise YouTubeDownloadError(
                    f"❌ Arquivo muito grande: {size_mb:.1f}MB\n"
                    f"Limite máximo: {max_mb:.1f}MB"
                )
            
            # Read file to memory
            with open(actual_file, 'rb') as f:
                video_data = f.read()
            
            # Determine if this is audio-only based on file extension
            is_audio_only = actual_file.lower().endswith(('.m4a', '.mp3', '.ogg', '.aac'))
            
            # Prepare metadata
            metadata = {
                'title': info.get('title', 'Video do YouTube'),
                'duration': info.get('duration'),
                'uploader': info.get('uploader', 'Desconhecido'),
                'upload_date': info.get('upload_date'),
                'view_count': info.get('view_count'),
                'like_count': info.get('like_count'),
                'file_size': len(video_data),
                'video_id': info.get('id'),
                'webpage_url': info.get('webpage_url', url),
                'format_used': format_string,
                'is_audio_only': is_audio_only
            }
            
            return video_data, metadata
            
        except asyncio.TimeoutError:
            raise YouTubeDownloadError("❌ Timeout: Download demorou mais que 5 minutos")
        except yt_dlp.DownloadError as e:
            error_msg = str(e).lower()
            logger.error("yt-dlp download error", extra={
                "error": str(e),
                "url": url,
                "format": format_string
            })
            if 'too large' in error_msg or 'file size' in error_msg:
                raise YouTubeDownloadError("❌ Arquivo muito grande para download")
            elif 'network' in error_msg or 'connection' in error_msg:
                raise YouTubeDownloadError("❌ Erro de conexão durante o download")
            elif 'requested format is not available' in error_msg:
                raise YouTubeDownloadError("❌ Nenhum formato disponível para este vídeo")
            else:
                raise YouTubeDownloadError(f"❌ Erro no download: {str(e)}")
        except Exception as e:
            logger.error("Error downloading video data", extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "url": url,
                "format": format_string
            })
            raise YouTubeDownloadError(f"❌ Erro inesperado durante o download: {str(e)}")
        finally:
            # Clean up any temporary files
            import glob
            temp_pattern = temp_path + "*"
            for temp_file in glob.glob(temp_pattern):
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                        logger.debug("Cleaned up temp file", extra={"file": temp_file})
                except Exception as e:
                    logger.warning("Failed to delete temp file", extra={
                        "error": str(e),
                        "file": temp_file
                    })
    
    async def _download_with_exhaustive_formats(self, url: str, info: Dict[str, Any], progress_callback: Optional[callable] = None) -> Tuple[bytes, Dict[str, Any]]:
        """Try downloading using intelligent format detection and priority testing"""
        
        # First, get available formats for this specific video
        available_formats = await self._get_available_formats(url)
        
        if not available_formats:
            raise YouTubeDownloadError("❌ Não foi possível obter lista de formatos disponíveis")
        
        logger.info("Available formats detected", extra={
            "url": url,
            "total_available": len(available_formats)
        })
        
        # Try formats in priority order - STOP at first success
        logger.info("Starting smart format testing", extra={
            "url": url,
            "total_available_formats": len(available_formats)
        })
        
        # PHASE 1: Try best video formats first
        video_result = await self._try_video_formats(url, info, available_formats, progress_callback)
        if video_result:
            return video_result
            
        # PHASE 2: Try audio-only as last resort
        audio_result = await self._try_audio_formats(url, info, available_formats, progress_callback)
        if audio_result:
            return audio_result
        
        # All formats failed
        logger.error("All format phases exhausted", extra={"url": url})
        
        raise YouTubeDownloadError(
            f"❌ Não foi possível baixar o vídeo em nenhum formato disponível.\n\n"
            f"Este vídeo pode ter restrições especiais, estar geo-bloqueado ou ter problemas técnicos.\n"
            f"Tente com outro vídeo ou verifique se o link está correto.\n\n"
            f"ID do vídeo: {info.get('id', 'desconhecido')}"
        )
    
    async def _try_video_formats(self, url: str, info: Dict[str, Any], available_formats: list, progress_callback: Optional[callable] = None) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        """Try video formats in priority order - stop at first success"""
        
        # Get prioritized video formats
        video_formats = []
        for fmt in available_formats:
            vcodec = fmt.get('vcodec', 'none')
            acodec = fmt.get('acodec', 'none') 
            width = fmt.get('width')
            height = fmt.get('height')
            filesize = fmt.get('filesize') or fmt.get('filesize_approx') or 0
            
            # Skip if not video
            if vcodec == 'none' or not width or not height:
                continue
            # Only skip if filesize is extremely large (give formats a chance)
            if filesize and filesize > self.max_file_size * 1.5:
                logger.info(f"Skipping format {fmt.get('format_id')} - extremely large", extra={
                    "format_id": fmt.get('format_id'),
                    "filesize": filesize,
                    "filesize_mb": filesize / (1024 * 1024),
                    "max_size_mb": self.max_file_size / (1024 * 1024),
                    "threshold_used": "1.5x limit"
                })
                continue
            elif filesize and filesize > self.max_file_size:
                logger.info(f"Format {fmt.get('format_id')} estimated large but will try", extra={
                    "format_id": fmt.get('format_id'),
                    "filesize": filesize,
                    "filesize_mb": filesize / (1024 * 1024),
                    "max_size_mb": self.max_file_size / (1024 * 1024),
                    "reason": "size_estimate_unreliable"
                })
                
            video_formats.append({
                'format_id': fmt.get('format_id'),
                'height': height,
                'vcodec': vcodec,
                'acodec': acodec,
                'ext': fmt.get('ext', ''),
                'filesize': filesize,
                'is_combined': acodec != 'none'
            })
        
        # Sort by priority
        video_formats.sort(key=lambda x: self._video_format_priority(x))
        
        logger.info("Trying video formats", extra={
            "url": url,
            "video_formats_available": len(video_formats)
        })
        
        # Try each format until one works
        for i, fmt in enumerate(video_formats, 1):
            try:
                format_id = fmt['format_id']
                logger.info(f"Trying video format {i}/{len(video_formats)}: {format_id}", extra={
                    "format": format_id,
                    "height": fmt['height'],
                    "is_combined": fmt['is_combined'],
                    "vcodec": fmt.get('vcodec', 'unknown'),
                    "acodec": fmt.get('acodec', 'unknown'),
                    "ext": fmt.get('ext', 'unknown')
                })
                
                result = await self._download_with_format_string(url, info, format_id, progress_callback)
                
                logger.info("Video format successful!", extra={
                    "format": format_id,
                    "attempt": i
                })
                return result
                
            except YouTubeDownloadError as e:
                error_msg = str(e).lower()
                if "muito grande" in error_msg:
                    logger.info(f"Format {format_id} too large, trying next")
                    continue
                elif "nenhum formato disponível" in error_msg or "requested format is not available" in error_msg:
                    logger.debug(f"Format {format_id} not available, trying next")
                    continue
                else:
                    logger.warning(f"Format {format_id} failed: {str(e)}")
                    continue
            except Exception as e:
                logger.warning(f"Unexpected error with format {format_id}: {str(e)}")
                continue
        
        logger.info("All video formats failed, falling back to audio")
        return None
    
    async def _try_audio_formats(self, url: str, info: Dict[str, Any], available_formats: list, progress_callback: Optional[callable] = None) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        """Try audio-only formats as last resort"""
        
        # Get audio-only formats
        audio_formats = []
        for fmt in available_formats:
            vcodec = fmt.get('vcodec', 'none')
            acodec = fmt.get('acodec', 'none')
            filesize = fmt.get('filesize') or fmt.get('filesize_approx') or 0
            
            # Skip if not audio-only
            if vcodec != 'none' or acodec == 'none':
                continue
            # Only skip if filesize is extremely large (give formats a chance)
            if filesize and filesize > self.max_file_size * 1.5:
                logger.info(f"Skipping audio format {fmt.get('format_id')} - extremely large", extra={
                    "format_id": fmt.get('format_id'),
                    "filesize": filesize,
                    "filesize_mb": filesize / (1024 * 1024),
                    "max_size_mb": self.max_file_size / (1024 * 1024),
                    "threshold_used": "1.5x limit"
                })
                continue
            elif filesize and filesize > self.max_file_size:
                logger.info(f"Audio format {fmt.get('format_id')} estimated large but will try", extra={
                    "format_id": fmt.get('format_id'),
                    "filesize": filesize,
                    "filesize_mb": filesize / (1024 * 1024),
                    "max_size_mb": self.max_file_size / (1024 * 1024),
                    "reason": "size_estimate_unreliable"
                })
                
            audio_formats.append({
                'format_id': fmt.get('format_id'),
                'ext': fmt.get('ext', ''),
                'acodec': acodec,
                'abr': fmt.get('abr', 0),
                'filesize': filesize
            })
        
        # Sort by priority
        audio_formats.sort(key=lambda x: self._audio_format_priority(x))
        
        logger.info("Trying audio-only formats", extra={
            "url": url,
            "audio_formats_available": len(audio_formats)
        })
        
        # Try each audio format
        for i, fmt in enumerate(audio_formats, 1):
            try:
                format_id = fmt['format_id']
                logger.info(f"Trying audio format {i}/{len(audio_formats)}: {format_id}", extra={
                    "format": format_id,
                    "ext": fmt['ext'],
                    "acodec": fmt['acodec']
                })
                
                result = await self._download_with_format_string(url, info, format_id, progress_callback)
                
                logger.info("Audio format successful!", extra={
                    "format": format_id,
                    "attempt": i
                })
                return result
                
            except YouTubeDownloadError as e:
                error_msg = str(e).lower()
                if "muito grande" in error_msg:
                    logger.info(f"Audio format {format_id} too large, trying next")
                    continue
                elif "nenhum formato disponível" in error_msg or "requested format is not available" in error_msg:
                    logger.debug(f"Audio format {format_id} not available, trying next")
                    continue
                else:
                    logger.warning(f"Audio format {format_id} failed: {str(e)}")
                    continue
            except Exception as e:
                logger.warning(f"Unexpected error with audio format {format_id}: {str(e)}")
                continue
        
        logger.error("All audio formats also failed")
        return None
    
    async def _get_available_formats(self, url: str) -> list:
        """Get list of all available formats for this video"""
        def _extract_formats():
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,
                'socket_timeout': 30,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info.get('formats', [])
        
        try:
            loop = asyncio.get_event_loop()
            formats = await asyncio.wait_for(
                loop.run_in_executor(None, _extract_formats),
                timeout=30
            )
            return formats
        except Exception as e:
            logger.warning("Failed to get available formats", extra={
                "url": url,
                "error": str(e)
            })
            return []
    
    
    def _video_format_priority(self, fmt: dict) -> tuple:
        """Calculate priority score for video format (lower = better)"""
        height = fmt.get('height', 0)
        ext = fmt.get('ext', '')
        vcodec = fmt.get('vcodec', '')
        filesize = fmt.get('filesize', 0)
        is_combined = fmt.get('is_combined', False)
        
        # Priority factors (lower = better)
        combined_bonus = 0 if is_combined else 5  # STRONGLY prefer combined formats
        codec_score = {'h264': 1, 'avc': 1, 'vp9': 2, 'av01': 3}.get(vcodec.lower(), 4)
        ext_score = {'mp4': 1, 'webm': 2, 'mkv': 3}.get(ext.lower(), 4)
        
        # Size preference - prioritize SMALLER sizes first for reliability
        # But also consider actual filesize if available
        size_score = 3
        if height:
            if height < 360:
                size_score = 5  # Skip very poor quality
            elif 360 <= height < 480:
                size_score = 1  # Start with 360p (smallest reasonable)
            elif 480 <= height < 720:
                size_score = 2  # Then 480p
            elif 720 <= height < 1080:
                size_score = 3  # Then 720p
            elif height >= 1080:
                size_score = 4  # Finally 1080p+ (likely to be large)
        
        # If we have filesize info, prioritize smaller files within same resolution
        filesize_penalty = 0
        if filesize:
            # Small penalty for larger files, but don't exclude them completely
            if filesize > self.max_file_size:
                filesize_penalty = 1  # Slightly lower priority but still try
            elif filesize > self.max_file_size * 0.8:
                filesize_penalty = 0.5  # Moderate penalty
        
        return (combined_bonus, size_score, codec_score, ext_score, filesize_penalty, -height)
    
    def _audio_format_priority(self, fmt: dict) -> tuple:
        """Calculate priority score for audio format (lower = better)"""
        ext = fmt.get('ext', '')
        acodec = fmt.get('acodec', '')
        abr = fmt.get('abr', 0)  # audio bitrate
        filesize = fmt.get('filesize', 0)
        
        # Priority factors (lower = better) 
        ext_score = {'m4a': 1, 'mp3': 2, 'aac': 3, 'webm': 4, 'ogg': 5}.get(ext.lower(), 6)
        codec_score = {'aac': 1, 'mp3': 2, 'opus': 3}.get(acodec.lower(), 4)
        
        # Prefer reasonable bitrates (128-256 kbps)
        bitrate_score = 2
        if abr:
            if 128 <= abr <= 256:
                bitrate_score = 1
            elif abr < 128:
                bitrate_score = 3
            elif abr > 256:
                bitrate_score = 4
        
        # If we have filesize info, prioritize smaller files
        filesize_penalty = 0
        if filesize:
            # Small penalty for larger files, but don't exclude them completely
            if filesize > self.max_file_size:
                filesize_penalty = 1  # Slightly lower priority but still try
            elif filesize > self.max_file_size * 0.8:
                filesize_penalty = 0.5  # Moderate penalty
        
        return (ext_score, codec_score, bitrate_score, filesize_penalty, -abr)
    
    async def get_video_info_only(self, url: str) -> Dict[str, Any]:
        """Get video information without downloading for preview"""
        try:
            if not YouTubeURLDetector.is_youtube_url(url):
                raise YouTubeDownloadError("URL não é um link válido do YouTube")
            
            normalized_url = YouTubeURLDetector.normalize_youtube_url(url)
            if not normalized_url:
                raise YouTubeDownloadError("Não foi possível processar o link do YouTube")
            
            info = await self._get_video_info(normalized_url)
            self._validate_video_constraints(info)
            
            # Return formatted info
            duration = info.get('duration', 0)
            duration_str = f"{duration//3600:02d}:{(duration%3600)//60:02d}:{duration%60:02d}" if duration else "Desconhecido"
            
            return {
                'title': info.get('title', 'Título não disponível'),
                'duration': duration,
                'duration_formatted': duration_str,
                'uploader': info.get('uploader', 'Canal desconhecido'),
                'view_count': info.get('view_count', 0),
                'upload_date': info.get('upload_date'),
                'thumbnail': info.get('thumbnail'),
                'description': info.get('description', '')[:200] + '...' if info.get('description', '') else '',
                'video_id': info.get('id'),
                'webpage_url': info.get('webpage_url', url),
                'is_downloadable': True
            }
            
        except YouTubeDownloadError:
            raise
        except Exception as e:
            logger.error("Error getting video info only", extra={"error": str(e)})
            raise YouTubeDownloadError("❌ Erro ao obter informações do vídeo")
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"


# Global service instance
youtube_service = YouTubeDownloadService()