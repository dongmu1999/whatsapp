"""本地日志配置，不记录聊天内容或凭据。"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("salespilot")
    if logger.handlers:
        return

    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        log_dir / "salespilot.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    logger.addHandler(handler)
    logger.propagate = False
