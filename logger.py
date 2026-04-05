import logging
import sys
from pathlib import Path
import config

# logs/ sits next to this file and is created at import time if it doesn't exist.
# The directory is gitignored — it should never be committed.
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """Return a named logger with a console handler and a file handler.

    Call once per module with the module name, e.g. get_logger("llm_client").
    Subsequent calls with the same name return the already-configured logger
    (the `if logger.handlers` guard prevents duplicate handlers).

    Console handler — level follows LOG_LEVEL from .env (default INFO).
    File handler   — always DEBUG so the full detail is on disk even when
                     the console is set to WARNING or higher.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # already configured; avoid adding duplicate handlers

    logger.setLevel(config.LOG_LEVEL)

    # Console: controlled by LOG_LEVEL so developers can silence noise easily
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(config.LOG_LEVEL)
    console_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))

    # File: always DEBUG — useful for post-mortem debugging without redeploying
    file_handler = logging.FileHandler(LOGS_DIR / "app.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, _DATE_FORMAT))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
