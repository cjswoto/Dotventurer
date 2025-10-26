import os
from datetime import datetime

from config import LOG_ENABLED, LOG_FILE_PATH


def log_line(message: str) -> None:
    """Append a timestamped debug entry when logging is enabled."""
    if not LOG_ENABLED:
        return

    directory = os.path.dirname(LOG_FILE_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as log_file:
        log_file.write(f"{timestamp} {message}\n")
