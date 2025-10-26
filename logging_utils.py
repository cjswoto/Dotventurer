"""Utility helpers for feature-flagged debug logging."""

from datetime import datetime
from pathlib import Path
from typing import Any

from config import LOG_ENABLED

LOG_FILE_PATH = Path("logs/debug.txt")


def log_debug(message: Any) -> None:
    """Append a timestamped debug entry when logging is enabled."""
    if not LOG_ENABLED:
        return
    LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().isoformat()
    with LOG_FILE_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{timestamp} {message}\n")
