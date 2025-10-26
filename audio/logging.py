"""Lightweight logging helpers guarded by the global LOG_ENABLED flag."""

from __future__ import annotations

import datetime
import os
from typing import Iterable

from config import LOG_ENABLED, LOG_FILE_PATH


def _ensure_log_dir() -> None:
    directory = os.path.dirname(LOG_FILE_PATH)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def log_lines(lines: Iterable[str]) -> None:
    """Write timestamped lines to the configured debug log when enabled."""
    if not LOG_ENABLED:
        return
    _ensure_log_dir()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as handle:
        for line in lines:
            handle.write(f"[{now}] {line}\n")
