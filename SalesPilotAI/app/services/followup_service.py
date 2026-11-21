"""跟进任务校验、状态流转与 AI 建议转换。"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.database.repositories.followup_repository import FollowupRepository
from app.models.followup import (
    PRIORITIES,
    Followup,
    FollowupDraft,
    FollowupNotFoundError,
    FollowupValidationError,
    normalize_due,
)
from app.models.message import utc_now_text

_MAX_CONTENT = 2000
_MAX_REASON = 200


class FollowupService:
    def __init__(self, repository: FollowupRepository):
        self.repository = repository

    def create(
        self,
        customer_id: int,
        due_at: datetime,
        reason: str,
        priority: str,
        content: str,
        *,
        analysis_id: int | None = None,
    ) -> Followup:
        if not isinstance(customer_id, int) or not self.repository.customer_exists(
            customer_id
        ):
            raise FollowupValidationError("请选择有效客户")
        if priority not in PRIORITIES:
            raise FollowupValidationError("不支持的优先级")
        clean_content = str(content or "").strip()
        if not clean_content:
            raise FollowupValidationError("跟进内容不能为空")
        if len(clean_content) > _MAX_CONTENT:
            raise FollowupValidationError(f"跟进内容不能超过 {_MAX_CONTENT} 个字符")
        clean_reason = str(reason or "").strip()
        if len(clean_reason) > _MAX_REASON:
            raise FollowupValidationError(f"跟进原因不能超过 {_MAX_REASON} 个字符")
        try:
            due_text = normalize_due(due_at)
        except (TypeError, ValueError) as exc:
            raise FollowupValidationError("跟进时间无效") from exc

        followup_id = self.repository.create(
            customer_id,
            due_text,
            clean_reason,
            priority,
            clean_content,
            analysis_id=analysis_id,
        )
        return self.get(followup_id)

    def get(self, followup_id: int) -> Followup:
        task = self.repository.get(followup_id)
        if task is None:
            raise FollowupNotFoundError("跟进任务不存在或已被删除")
        return task

    def list(
        self,
        *,
        customer_id: int | None = None,
        status: str | None = None,
    ) -> list[Followup]:
        return self.repository.list(customer_id=customer_id, status=status)

    def record_result(self, followup_id: int, result: str) -> Followup:
        task = self.get(followup_id)
        self._require_pending(task)
        clean = str(result or "").strip()
        if not clean:
            raise FollowupValidationError("跟进结果不能为空")
        if len(clean) > _MAX_CONTENT:
            raise FollowupValidationError(f"跟进结果不能超过 {_MAX_CONTENT} 个字符")
        self.repository.record_result(followup_id, clean)
        return self.get(followup_id)

    def complete(self, followup_id: int, result: str = "") -> Followup:
        task = self.get(followup_id)
        self._require_pending(task)
        clean = str(result or "").strip()
        if len(clean) > _MAX_CONTENT:
            raise FollowupValidationError(f"跟进结果不能超过 {_MAX_CONTENT} 个字符")
        self.repository.complete(followup_id, clean, utc_now_text())
        return self.get(followup_id)

    def cancel(self, followup_id: int) -> Followup:
        task = self.get(followup_id)
        self._require_pending(task)
        self.repository.cancel(followup_id, utc_now_text())
        return self.get(followup_id)

    def overdue(self, now: datetime | None = None) -> list[Followup]:
        reference = now or datetime.now().astimezone()
        return self.repository.pending_due_before(normalize_due(reference))

    def due_today(self, now: datetime | None = None) -> list[Followup]:
        reference = now or datetime.now().astimezone()
        local = reference.astimezone() if reference.tzinfo else reference
        start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        return self.repository.pending_due_between(
            normalize_due(start), normalize_due(start + timedelta(days=1))
        )

    def suggest_from_analysis(
        self,
        customer_id: int,
        analysis,
        *,
        now: datetime | None = None,
    ) -> FollowupDraft | None:
        """只生成待用户确认的草稿，绝不自动写入跟进任务。"""
        if not analysis.followup_required:
            return None
        days = analysis.followup_due_days
        if days is None:
            days = 3
        reference = now or datetime.now().astimezone()
        content = str(analysis.followup_suggestion or "").strip() or "跟进客户沟通进展"
        return FollowupDraft(
            customer_id=customer_id,
            due_at=normalize_due(reference + timedelta(days=days)),
            reason="AI 建议跟进",
            priority="medium",
            content=content,
        )

    @staticmethod
    def _require_pending(task: Followup) -> None:
        if task.status == "completed":
            raise FollowupValidationError("该跟进任务已完成，不能重复操作")
        if task.status == "cancelled":
            raise FollowupValidationError("该跟进任务已取消，不能继续操作")
