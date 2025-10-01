"""Structured logging configuration for TastyTrade MCP."""
import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from tastytrade_mcp.config.settings import get_settings

settings = get_settings()


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]:
                log_obj[key] = value
        
        return json.dumps(log_obj)


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output."""
    
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
        
        # Format the message
        message = super().format(record)
        
        # Reset level name for other handlers
        record.levelname = levelname
        
        return message


class SentryHandler(logging.Handler):
    """
    Custom handler for Sentry integration.
    In production, this would send errors to Sentry.
    """
    
    def __init__(self):
        """Initialize Sentry handler."""
        super().__init__()
        self.sentry_dsn = os.getenv("SENTRY_DSN")
        self.environment = settings.environment
        
        if self.sentry_dsn and settings.environment != "development":
            # In production, initialize Sentry SDK here
            # import sentry_sdk
            # sentry_sdk.init(dsn=self.sentry_dsn, environment=self.environment)
            pass
    
    def emit(self, record: logging.LogRecord) -> None:
        """Send log record to Sentry."""
        if not self.sentry_dsn or settings.environment == "development":
            return
        
        if record.levelno >= logging.ERROR:
            # In production, send to Sentry
            # sentry_sdk.capture_message(record.getMessage(), level=record.levelname.lower())
            pass


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    use_json: bool = False,
) -> None:
    """
    Set up logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        use_json: Use JSON formatting for logs
    """
    # Determine log level
    if log_level is None:
        log_level = settings.log_level
    
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    # Create logs directory if needed
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    
    if use_json or settings.environment == "production":
        # Use structured logging in production
        console_formatter = StructuredFormatter()
    else:
        # Use colored formatter for development
        console_formatter = ColoredFormatter(
            fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
        file_handler.setLevel(numeric_level)
        
        # Always use JSON for file logs
        file_formatter = StructuredFormatter()
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Sentry handler for production errors
    if settings.environment != "development":
        sentry_handler = SentryHandler()
        sentry_handler.setLevel(logging.ERROR)
        root_logger.addHandler(sentry_handler)
    
    # Configure specific loggers
    # Reduce noise from libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured",
        extra={
            "log_level": log_level,
            "environment": settings.environment,
            "use_json": use_json or settings.environment == "production",
            "log_file": log_file,
        }
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with structured logging support.
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    **kwargs: Any
) -> None:
    """
    Log an HTTP request with structured data.
    
    Args:
        logger: Logger instance
        method: HTTP method
        path: Request path
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        **kwargs: Additional fields to log
    """
    logger.info(
        f"{method} {path} - {status_code}",
        extra={
            "http_method": method,
            "http_path": path,
            "http_status": status_code,
            "duration_ms": duration_ms,
            **kwargs
        }
    )


def log_error(
    logger: logging.Logger,
    error: Exception,
    context: str,
    **kwargs: Any
) -> None:
    """
    Log an error with structured data.
    
    Args:
        logger: Logger instance
        error: Exception that occurred
        context: Context where error occurred
        **kwargs: Additional fields to log
    """
    logger.error(
        f"Error in {context}: {str(error)}",
        exc_info=True,
        extra={
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            **kwargs
        }
    )