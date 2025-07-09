import logging
import sys
from typing import Dict, Any
import json
from datetime import datetime
import os
from pathlib import Path


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, "extra"):
            log_data.update(record.extra)
            
        return json.dumps(log_data, ensure_ascii=False)


def setup_youtube_logging(log_file: str = "logs/youtube_downloader.log") -> None:
    """Setup dedicated logging for YouTube downloader"""
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create YouTube-specific logger
    youtube_logger = logging.getLogger("app.services.youtube_downloader")
    youtube_logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers to avoid duplicates
    youtube_logger.handlers.clear()
    
    # File handler for YouTube logs
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(StructuredFormatter())
    youtube_logger.addHandler(file_handler)
    
    # Don't propagate to root logger to avoid console spam
    youtube_logger.propagate = False
    
    youtube_logger.info("YouTube downloader logging initialized", extra={
        "log_file": log_file
    })


def setup_logging(debug: bool = False, log_file: str = None) -> None:
    """Setup structured logging with optional file output"""
    level = logging.DEBUG if debug else logging.INFO
    
    # Remove default handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Create handlers list
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredFormatter())
    handlers.append(console_handler)
    
    # File handler if specified
    if log_file:
        # Create logs directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(StructuredFormatter())
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True
    )
    
    # Set specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    
    logger = logging.getLogger(__name__)
    logger.info("Structured logging configured", extra={
        "debug_mode": debug,
        "level": level,
        "log_file": log_file
    })
