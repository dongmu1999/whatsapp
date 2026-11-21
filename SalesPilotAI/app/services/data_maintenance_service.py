"""本地数据维护：聊天保留期限、临时截图清理与全部数据清空。"""

from __future__ import annotations

import logging
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.database.connection import Database

logger = logging.getLogger(__name__)

RETENTION_KEY = "chat_retention_days"
MAX_RETENTION_DAYS = 3650
CAPTURE_PATTERN = "salespilot-capture-*.png"
CLEARABLE_TABLES = (
    "reply_suggestions",
    "analyses",
    "followups",
    "customer_memories",
    "messages",
    "conversations",
    "knowledge_documents",
    "products",
    "customers",
    "api_usage",
)


class DataMaintenanceService:
    """所有清理操作只作用于本地 SQLite 和本地临时文件。"""

    def __init__(
        self,
        database: Database,
        data_dir: str | Path,
        *,
        settings=None,
        temp_dir: str | Path | None = None,
    ):
        self.database = database
        self.data_dir = Path(data_dir).expanduser()
        self.settings = settings
        self.temp_dir = Path(temp_dir) if temp_dir is not None else Path(
            tempfile.gettempdir()
        )
        self._retention_days = 0

    def get_retention_days(self) -> int:
        raw = (
            self.settings.get(RETENTION_KEY, "0")
            if self.settings is not None
            else str(self._retention_days)
        )
        try:
            days = int(raw)
        except (TypeError, ValueError):
            return 0
        return max(0, min(MAX_RETENTION_DAYS, days))

    def set_retention_days(self, days) -> int:
        if isinstance(days, bool):
            raise ValueError("聊天保留天数必须是 0 到 3650 之间的整数")
        if isinstance(days, float) and not days.is_integer():
            raise ValueError("聊天保留天数必须是 0 到 3650 之间的整数")
        try:
            value = int(days)
        except (TypeError, ValueError) as exc:
            raise ValueError("聊天保留天数必须是 0 到 3650 之间的整数") from exc
        if not 0 <= value <= MAX_RETENTION_DAYS:
            raise ValueError("聊天保留天数必须是 0 到 3650 之间的整数")
        self._retention_days = value
        if self.settings is not None:
            self.settings.set(RETENTION_KEY, str(value))
        logger.info("聊天保留期限已设置为 %s 天（0 表示永久）", value)
        return value

    def apply_retention(self, now: datetime | None = None) -> int:
        days = self.get_retention_days()
        if days <= 0:
            return 0
        current = self._utc(now)
        cutoff = current - timedelta(days=days)
        cutoff_text = self._format_utc(cutoff)
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                DELETE FROM conversations
                WHERE COALESCE(last_message_at, created_at) < ?
                """,
                (cutoff_text,),
            )
            deleted = max(cursor.rowcount or 0, 0)
        if deleted:
            logger.info("已按保留期限清理 %s 个过期聊天会话", deleted)
        return deleted

    def cleanup_temp_screenshots(
        self, now: datetime | None = None, max_age_hours: int = 24
    ) -> int:
        cutoff = self._utc(now).timestamp() - max(0, int(max_age_hours)) * 3600
        removed = 0
        try:
            candidates = list(self.temp_dir.glob(CAPTURE_PATTERN))
        except OSError:
            logger.exception("读取临时截图目录失败")
            return 0
        for path in candidates:
            try:
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError:
                logger.warning("清理临时截图失败：%s", path.name)
        if removed:
            logger.info("已清理 %s 个过期临时截图", removed)
        return removed

    def clear_all_data(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        with self.database.transaction() as connection:
            for table in CLEARABLE_TABLES:
                cursor = connection.execute(f"DELETE FROM {table}")
                counts[table] = max(cursor.rowcount or 0, 0)
        counts["knowledge_files"] = self._clear_knowledge_files()
        logger.warning("已清空全部本地业务数据，系统设置与迁移记录保留")
        return counts

    def _clear_knowledge_files(self) -> int:
        directory = self.data_dir / "knowledge"
        if not directory.is_dir():
            return 0
        removed = 0
        for path in directory.rglob("*"):
            if not path.is_file():
                continue
            try:
                path.unlink()
                removed += 1
            except OSError:
                logger.warning("删除知识库副本失败：%s", path.name)
        return removed

    @staticmethod
    def _utc(value: datetime | None) -> datetime:
        current = value or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc)

    @staticmethod
    def _format_utc(value: datetime) -> str:
        return f"{value:%Y-%m-%dT%H:%M:%S}.{value.microsecond // 1000:03d}Z"
