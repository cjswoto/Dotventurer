"""Utility helpers shared across audio modules."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from config import LOG_ENABLED, LOG_FILE


def log_debug(message: str) -> None:
    """Append a timestamped debug entry when logging is enabled."""

    if not LOG_ENABLED:
        return

    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")


def db_to_gain(db_value: float) -> float:
    """Convert a decibel value to a linear gain scalar."""

    return 10 ** (db_value / 20.0)


def clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` to ``[low, high]``."""

    return max(low, min(value, high))


def require(condition: bool, message: str) -> None:
    """Raise ``ValueError`` with ``message`` when ``condition`` is False."""

    if not condition:
        raise ValueError(message)


SAMPLE_RATE = 48_000
