"""Helper utilities for optional debug logging."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from config import LOG_ENABLED, LOG_FILE


def log_debug(message: str) -> None:
    """Append a timestamped message to the debug log when enabled."""
    if not LOG_ENABLED:
        return
    path = Path(LOG_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")
