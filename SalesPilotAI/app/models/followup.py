"""跟进任务模型、状态与本地时间转换。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

PRIORITIES = ("low", "medium", "high")
PRIORITY_LABELS = {"low": "低", "medium": "中", "high": "高"}
STATUSES = ("pending", "completed", "cancelled")
STATUS_LABELS = {"pending": "待办", "completed": "已完成", "cancelled": "已取消"}


class FollowupValidationError(ValueError):
    """跟进任务不满足本地保存或状态流转条件。"""


class FollowupNotFoundError(LookupError):
    """跟进任务不存在。"""


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.astimezone()
    return value.astimezone(timezone.utc)


def normalize_due(value: datetime) -> str:
    """把用户本地日期时间转换为 UTC 文本存储。"""
    if not isinstance(value, datetime):
        raise FollowupValidationError("跟进时间无效")
    return _as_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_due(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_due_local(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return parse_due(value).astimezone().strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return str(value)


@dataclass(frozen=True)
class Followup:
    id: int
    customer_id: int
    due_at: str
    customer_name: str = ""
    analysis_id: int | None = None
    reason: str = ""
    priority: str = "medium"
    content: str = ""
    result: str = ""
    status: str = "pending"
    completed_at: str | None = None
    cancelled_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def due_datetime(self) -> datetime:
        return parse_due(self.due_at)

    @property
    def due_local_text(self) -> str:
        return format_due_local(self.due_at)

    def is_overdue(self, now: datetime | None = None) -> bool:
        if self.status != "pending":
            return False
        reference = _as_utc(now or datetime.now().astimezone())
        return self.due_datetime < reference

    @classmethod
    def from_row(cls, row) -> "Followup":
        return cls(
            id=int(row["id"]),
            customer_id=int(row["customer_id"]),
            due_at=str(row["due_at"]),
            customer_name=str(row["customer_name"] or ""),
            analysis_id=row["analysis_id"],
            reason=str(row["reason"] or ""),
            priority=str(row["priority"]),
            content=str(row["content"] or ""),
            result=str(row["result"] or ""),
            status=str(row["status"]),
            completed_at=row["completed_at"],
            cancelled_at=row["cancelled_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True)
class FollowupDraft:
    """AI 建议的跟进草稿，必须由用户确认后才会写入数据库。"""

    customer_id: int
    due_at: str
    reason: str
    priority: str
    content: str
    analysis_id: int | None = None
