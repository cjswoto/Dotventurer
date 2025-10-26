"""Lightweight logging utilities guarded by a feature flag."""

from __future__ import annotations

import os
import time

from config import LOG_ENABLED, LOG_FILE


def log_debug(message: str) -> None:
    """Append a timestamped debug entry when logging is enabled."""
    if not LOG_ENABLED:
        return
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with open(LOG_FILE, "a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")
