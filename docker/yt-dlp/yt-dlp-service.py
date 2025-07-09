#!/usr/bin/env python3
"""
Standalone yt-dlp service API
This service can be updated independently of the main application
"""

import asyncio
import logging
import tempfile
import os
from typing import Dict, Any, Optional, Tuple
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import yt_dlp
import subprocess
import sys

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="yt-dlp Service", version="1.0.0")

class DownloadRequest(BaseModel):
    url: str
    max_file_size: int = 200 * 1024 * 1024  # 200MB default
    max_duration: int = 1800  # 30 minutes
    quality: str = "best[ext=mp4][height<=720]/best[ext=mp4]/best[height<=720]/best"

class DownloadResponse(BaseModel):
    success: bool
    file_data: Optional[str] = None  # Base64 encoded
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class UpdateResponse(BaseModel):
    success: bool
    old_version: str
    new_version: str
    message: str

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        version = yt_dlp.version.__version__
        return {"status": "healthy", "yt_dlp_version": version}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.post("/update")
async def update_yt_dlp():
    """Update yt-dlp to latest version"""
    try:
        # Get current version
        old_version = yt_dlp.version.__version__
        
        # Update yt-dlp
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            return UpdateResponse(
                success=False,
                old_version=old_version,
                new_version=old_version,
                message=f"Update failed: {result.stderr}"
            )
        
        # Reload the module
        import importlib
        importlib.reload(yt_dlp)
        
        new_version = yt_dlp.version.__version__
        
        return UpdateResponse(
            success=True,
            old_version=old_version,
            new_version=new_version,
            message=f"Updated from {old_version} to {new_version}"
        )
        
    except Exception as e:
        return UpdateResponse(
            success=False,
            old_version="unknown",
            new_version="unknown",
            message=f"Update error: {str(e)}"
        )

@app.post("/download")
async def download_video(request: DownloadRequest) -> DownloadResponse:
    """Download video using yt-dlp"""
    temp_path = None
    
    try:
        # Create temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix='.tmp', prefix='ytdlp_')
        os.close(temp_fd)
        
        # Configure yt-dlp options
        ydl_opts = {
            'format': request.quality,
            'outtmpl': temp_path + '.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            'max_filesize': request.max_file_size,
            'overwrites': True,
            'nocheckcertificate': True,
            'prefer_insecure': True,
        }
        
        # Extract info first
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info = ydl.extract_info(request.url, download=False)
            
            # Validate constraints
            if info.get('duration', 0) > request.max_duration:
                return DownloadResponse(
                    success=False,
                    error=f"Video too long: {info.get('duration')}s > {request.max_duration}s"
                )
        
        # Download video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([request.url])
        
        # Find downloaded file
        import glob
        downloaded_files = glob.glob(temp_path + '*')
        
        if not downloaded_files:
            return DownloadResponse(
                success=False,
                error="No file was downloaded"
            )
        
        actual_file = downloaded_files[0]
        
        # Read file and encode as base64
        import base64
        with open(actual_file, 'rb') as f:
            file_data = base64.b64encode(f.read()).decode('utf-8')
        
        # Clean up
        os.unlink(actual_file)
        
        # Prepare metadata
        metadata = {
            'title': info.get('title', 'Unknown'),
            'duration': info.get('duration'),
            'uploader': info.get('uploader', 'Unknown'),
            'upload_date': info.get('upload_date'),
            'view_count': info.get('view_count'),
            'video_id': info.get('id'),
            'webpage_url': info.get('webpage_url', request.url),
            'file_size': len(base64.b64decode(file_data)),
            'is_audio_only': actual_file.lower().endswith(('.m4a', '.mp3', '.ogg', '.aac'))
        }
        
        return DownloadResponse(
            success=True,
            file_data=file_data,
            metadata=metadata
        )
        
    except yt_dlp.DownloadError as e:
        error_msg = str(e).lower()
        if 'private' in error_msg:
            error = "Video is private or not available"
        elif 'not available' in error_msg:
            error = "Video not available in your region"
        elif 'removed' in error_msg or 'deleted' in error_msg:
            error = "Video was removed or deleted"
        else:
            error = f"Download error: {str(e)}"
        
        return DownloadResponse(success=False, error=error)
        
    except Exception as e:
        return DownloadResponse(success=False, error=f"Unexpected error: {str(e)}")
        
    finally:
        # Clean up temp files
        if temp_path:
            import glob
            for temp_file in glob.glob(temp_path + '*'):
                try:
                    os.unlink(temp_file)
                except:
                    pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)