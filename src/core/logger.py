"""
Sistema de logging estructurado para el asistente RAG.
"""

import logging
import logging.handlers
from pathlib import Path
from src.core.config import settings, PROJECT_ROOT

_initialized = False


def setup_logging():
    """Configura handlers de consola y archivo rotativo."""
    global _initialized
    if _initialized:
        return logging.getLogger("assistant")

    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "assistant.log"

    logger = logging.getLogger("assistant")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # File Handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    _initialized = True
    return logger


def get_logger(module_name: str) -> logging.Logger:
    """Obtiene un logger subordinado para un módulo."""
    if not _initialized:
        setup_logging()
    return logging.getLogger(f"assistant.{module_name}")
