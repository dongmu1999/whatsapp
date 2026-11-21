"""SQLite 连接与事务管理。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class Database:
    """持有单个 SQLite 连接，并统一启用数据完整性配置。"""

    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

        self._closed = True
        self._connect()

    def _connect(self) -> None:
        # 使用自动提交模式，事务仅由 transaction() 和迁移器显式控制。
        self.connection = sqlite3.connect(
            self.path, timeout=5.0, isolation_level=None
        )
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA busy_timeout = 5000")
        if self.path != ":memory:":
            self.connection.execute("PRAGMA journal_mode = WAL")
            self.connection.execute("PRAGMA synchronous = NORMAL")
        self._closed = False

    def reconnect(self) -> None:
        """关闭并重新打开同一路径的连接，用于恢复数据库文件后继续使用。"""
        self.close()
        self._connect()

    def initialize(self) -> list[int]:
        from app.database.migrations import MigrationManager

        return MigrationManager(self.connection).migrate()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """提供明确提交与回滚的短事务。"""
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            yield self.connection
        except Exception:
            self.connection.rollback()
            raise
        else:
            self.connection.commit()

    def close(self) -> None:
        if not self._closed:
            try:
                self.connection.close()
            except sqlite3.Error:
                pass
            self._closed = True

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
