"""Lightweight logging helper governed by a feature flag."""

from __future__ import annotations

from datetime import datetime
import os

from config import LOG_ENABLED, LOG_FILE_PATH


def log_debug(label: str, message: str) -> None:
    """Append a timestamped line to the debug log when enabled."""
    if not LOG_ENABLED:
        return

    directory = os.path.dirname(LOG_FILE_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)

    timestamp = datetime.utcnow().isoformat(timespec="milliseconds")
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} [{label}] {message}\n")
