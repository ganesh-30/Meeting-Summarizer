import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path

# Constants
LOG_DIR = 'logs'
LOG_FILE = f"{datetime.now().strftime('%m_%d_%Y_%H_%M_%S')}.log"
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5MB
BACKUP_COUNT = 3

# Find project root — the folder containing pyproject.toml
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
log_dir_path = PROJECT_ROOT / LOG_DIR
log_dir_path.mkdir(parents=True, exist_ok=True)
log_file_path = log_dir_path / LOG_FILE

def configure_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "[ %(asctime)s ] %(name)s - %(levelname)s - %(message)s"
    )

    # File handler — captures everything
    file_handler = RotatingFileHandler(
        log_file_path, 
        maxBytes=MAX_LOG_SIZE, 
        backupCount=BACKUP_COUNT
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # Console handler — only INFO and above
    console_handler = logging.StreamHandler(
        stream=open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
    )
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

def get_logger(name: str) -> logging.Logger:
    """
    Call this in every module.
    Usage: logger = get_logger(__name__)
    """
    return logging.getLogger(name)

# Configure once at import time
configure_logger()