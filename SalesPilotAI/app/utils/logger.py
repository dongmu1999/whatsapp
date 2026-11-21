"""本地日志配置，不记录聊天内容或凭据。"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class _AppLogFilter(logging.Filter):
    """只记录本应用日志，避免第三方库把无关内容写入本地日志。"""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name == "app" or record.name.startswith(
            ("app.", "salespilot")
        )


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        log_dir / "salespilot.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    handler.addFilter(_AppLogFilter())
    root.addHandler(handler)
