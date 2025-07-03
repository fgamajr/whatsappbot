import logging
import sys
from typing import Dict, Any
import json
from datetime import datetime
from app.utils.secure_logging import SecureLogFormatter, SecureLogger


class StructuredFormatter(SecureLogFormatter):
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
        
        # Add extra fields if present (sanitized)
        if hasattr(record, "extra"):
            sanitized_extra = SecureLogger.sanitize_dict(record.extra)
            log_data.update(sanitized_extra)
        
        # Convert to JSON and apply parent class sanitization
        json_str = json.dumps(log_data, ensure_ascii=False)
        
        # Apply additional sanitization from parent class
        return super(SecureLogFormatter, self).format(
            logging.LogRecord(
                name=record.name,
                level=record.levelno,
                pathname=record.pathname,
                lineno=record.lineno,
                msg=json_str,
                args=(),
                exc_info=None
            )
        )


def setup_logging(debug: bool = False) -> None:
    """Setup structured logging"""
    level = logging.DEBUG if debug else logging.INFO
    
    # Remove default handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Create structured handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=[handler],
        force=True
    )
    
    # Set specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    
    logger = logging.getLogger(__name__)
    logger.info("Structured logging configured", extra={
        "debug_mode": debug,
        "level": level
    })
