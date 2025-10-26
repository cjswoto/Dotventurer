"""Internal logging helpers for optional trace output."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from config import AUDIO_LOG_ENABLED

_LOG_PATH = Path("logs/debug.txt")


def log_line(message: str, *, context: str | None = None, data: dict[str, Any] | None = None) -> None:
    """Write a timestamped line to the debug log when enabled."""
    if not AUDIO_LOG_ENABLED:
        return
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = message
    if context:
        payload = f"[{context}] {payload}"
    if data:
        extras = ", ".join(f"{k}={v}" for k, v in data.items())
        payload = f"{payload} ({extras})"
    with _LOG_PATH.open("a", encoding="utf-8") as handle:
        stamp = datetime.utcnow().isoformat(timespec="milliseconds")
        handle.write(f"{stamp} {payload}\n")
