"""Shared logging helpers for the audio package."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from config import LOG_ENABLED

_LOG_PATH = Path("logs/debug.txt")


def log_line(message: str) -> None:
    """Write a timestamped message when logging is enabled."""
    if not LOG_ENABLED:
        return
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().isoformat(timespec="milliseconds")
    with _LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")


def log_loop(header: str, items: Iterable[str]) -> None:
    """Emit each item in a loop for detailed tracing when enabled."""
    if not LOG_ENABLED:
        return
    log_line(header)
    for entry in items:
        log_line(f"  {entry}")
