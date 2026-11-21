from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from app.database.repositories.customer_repository import CustomerRepository
from app.database.repositories.followup_repository import FollowupRepository
from app.models.analysis import parse_analysis_json
from app.models.followup import (
    FollowupNotFoundError,
    FollowupValidationError,
    format_due_local,
    normalize_due,
)
from app.services.customer_service import CustomerService
from app.services.followup_service import FollowupService
from test_analysis import payload


def _services(database):
    customers = CustomerService(CustomerRepository(database))
    followups = FollowupService(FollowupRepository(database))
    return customers, followups


def _customer(service, name):
    return service.create({"name": name})


def _local_now() -> datetime:
    return datetime.now().astimezone()


def _analysis(**overrides):
    data = payload()
    data.update(overrides)
    return parse_analysis_json(json.dumps(data, ensure_ascii=False))


def test_task_is_created_pending_and_visible_for_its_customer(database):
    customers, followups = _services(database)
    alice = _customer(customers, "Alice")
    due = _local_now() + timedelta(hours=2)

    task = followups.create(
        alice.id,
        due,
        "确认报价反馈",
        "high",
        "询问客户是否收到报价并需要补充资料",
    )

    assert task.status == "pending"
    assert task.priority == "high"
    assert task.customer_name == "Alice"
    assert task.reason == "确认报价反馈"
    assert task.due_at.endswith("Z")
    assert followups.list(customer_id=alice.id)[0].id == task.id
    assert followups.get(task.id).content == "询问客户是否收到报价并需要补充资料"


def test_task_validation_rejects_invalid_input(database):
    customers, followups = _services(database)
    alice = _customer(customers, "Alice")
    due = _local_now() + timedelta(hours=1)

    with pytest.raises(FollowupValidationError, match="请选择有效客户"):
        followups.create(999, due, "原因", "medium", "内容")
    with pytest.raises(FollowupValidationError, match="不支持的优先级"):
        followups.create(alice.id, due, "原因", "urgent", "内容")
    with pytest.raises(FollowupValidationError, match="跟进内容不能为空"):
        followups.create(alice.id, due, "原因", "medium", "   ")
    with pytest.raises(FollowupValidationError, match="跟进原因不能超过"):
        followups.create(alice.id, due, "原" * 201, "medium", "内容")
    with pytest.raises(FollowupNotFoundError):
        followups.complete(999, "结果")


def test_record_result_complete_and_cancel_follow_state_rules(database):
    customers, followups = _services(database)
    alice = _customer(customers, "Alice")
    due = _local_now() + timedelta(hours=1)
    task = followups.create(alice.id, due, "跟进", "medium", "确认交期")

    recorded = followups.record_result(task.id, "客户说稍后回复")
    assert recorded.status == "pending"
    assert recorded.result == "客户说稍后回复"

    completed = followups.complete(task.id)
    assert completed.status == "completed"
    assert completed.completed_at
    assert completed.result == "客户说稍后回复"
    with pytest.raises(FollowupValidationError, match="已完成"):
        followups.complete(task.id)

    cancelled = followups.create(alice.id, due, "取消测试", "low", "无需跟进")
    assert followups.cancel(cancelled.id).status == "cancelled"
    with pytest.raises(FollowupValidationError, match="已取消"):
        followups.record_result(cancelled.id, "迟到记录")


def test_status_filter_order_and_overdue_detection(database):
    customers, followups = _services(database)
    alice = _customer(customers, "Alice")
    bob = _customer(customers, "Bob")
    now = _local_now()

    later = followups.create(alice.id, now + timedelta(days=2), "稍后", "low", "后续")
    sooner = followups.create(alice.id, now + timedelta(hours=1), "稍早", "high", "优先")
    followups.complete(later.id, "已处理")
    overdue = followups.create(bob.id, now - timedelta(days=1), "逾期", "medium", "补跟进")

    pending = followups.list(status="pending")
    assert [task.id for task in pending] == [overdue.id, sooner.id]
    assert [task.id for task in followups.list(customer_id=alice.id)] == [
        sooner.id,
        later.id,
    ]
    assert [task.id for task in followups.overdue(now=now)] == [overdue.id]
    assert overdue.is_overdue(now)
    assert not sooner.is_overdue(now)
    assert format_due_local(overdue.due_at) != "—"


def test_due_today_uses_local_calendar_day(database):
    customers, followups = _services(database)
    alice = _customer(customers, "Alice")
    local_tz = _local_now().tzinfo
    now = datetime(2026, 11, 21, 8, 0, tzinfo=local_tz)

    today = followups.create(
        alice.id, datetime(2026, 11, 21, 10, 0, tzinfo=local_tz), "今日", "high", "电话"
    )
    tomorrow = followups.create(
        alice.id, datetime(2026, 11, 22, 10, 0, tzinfo=local_tz), "明日", "low", "邮件"
    )

    assert [task.id for task in followups.due_today(now=now)] == [today.id]
    assert all(task.id != tomorrow.id for task in followups.due_today(now=now))


def test_ai_suggestion_builds_draft_without_creating_task(database):
    customers, followups = _services(database)
    alice = _customer(customers, "Alice")
    now = _local_now()
    analysis = _analysis(
        followup_required=True,
        followup_suggestion="礼貌确认客户是否收到报价并需要补充资料",
        followup_due_days=3,
    )

    draft = followups.suggest_from_analysis(alice.id, analysis, now=now)

    assert draft is not None
    assert draft.customer_id == alice.id
    assert draft.due_at == normalize_due(now + timedelta(days=3))
    assert draft.content == "礼貌确认客户是否收到报价并需要补充资料"
    assert draft.priority == "medium"
    assert followups.list() == []

    not_needed = _analysis(followup_required=False)
    assert followups.suggest_from_analysis(alice.id, not_needed, now=now) is None


def test_analysis_json_validates_followup_due_days_range():
    accepted = _analysis(followup_required=True, followup_due_days=7)
    assert accepted.followup_due_days == 7

    with pytest.raises(Exception, match="结构化结果无效"):
        _analysis(followup_due_days=31)
