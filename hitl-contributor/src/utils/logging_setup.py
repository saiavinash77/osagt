"""
Logging setup — call configure_logging() once at startup.
Writes structured logs to both console (Rich) and a rotating file.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler


def configure_logging(log_level: str = "INFO", log_file: str = "logs/agent.log") -> None:
    """
    Set up root logger with:
    - Rich console handler (pretty, coloured output)
    - Rotating file handler (JSON-ish structured lines, max 5 MB × 3 files)
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Ensure log directory exists
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove any existing handlers (e.g. from basicConfig calls)
    root_logger.handlers.clear()

    # ── Console handler (Rich) ────────────────────────────────────────────
    console_handler = RichHandler(
        rich_tracebacks=True,
        show_path=False,
        markup=True,
    )
    console_handler.setLevel(numeric_level)
    root_logger.addHandler(console_handler)

    # ── File handler ─────────────────────────────────────────────────────
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(numeric_level)
    file_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Quieten noisy third-party loggers
    for noisy in ("httpcore", "httpx", "urllib3", "github"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        f"Logging configured — level={log_level}, file={log_file}"
    )
