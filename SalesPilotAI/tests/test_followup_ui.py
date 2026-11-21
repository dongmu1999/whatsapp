from __future__ import annotations

import json
from datetime import datetime, timedelta

from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtWidgets import QLabel

from app.database.repositories.customer_repository import CustomerRepository
from app.database.repositories.followup_repository import FollowupRepository
from app.models.analysis import parse_analysis_json
from app.services.customer_service import CustomerService
from app.services.followup_service import FollowupService
from app.ui.analysis_result import AnalysisResultWidget
from app.ui.followup_page import FollowupPage
from app.ui.main_window import MainWindow
from test_analysis import payload


def _services(database):
    customers = CustomerService(CustomerRepository(database))
    followups = FollowupService(FollowupRepository(database))
    return customers, followups


def _customer(service, name):
    return service.create({"name": name})


def test_create_task_from_form_and_complete_with_result(application, database):
    customers, followups = _services(database)
    alice = _customer(customers, "Alice")
    page = FollowupPage(followups, customers)
    page.refresh_customers()
    page.customer_combo.setCurrentIndex(page.customer_combo.findData(alice.id))
    page.date_edit.setDate(QDate.currentDate().addDays(2))
    page.time_edit.setTime(QTime(9, 30))
    page.reason_edit.setText("报价跟进")
    page.priority_combo.setCurrentIndex(page.priority_combo.findData("high"))
    page.content_edit.setPlainText("确认客户是否收到报价")
    changed = []
    page.followups_changed.connect(lambda: changed.append(True))

    assert page.create_task()
    assert page.task_table.rowCount() == 1
    assert page.task_table.item(0, 0).text() == "Alice"
    assert page.task_table.item(0, 2).text() == "高"
    assert page.task_table.item(0, 3).text() == "报价跟进"
    assert page.task_table.item(0, 4).text() == "确认客户是否收到报价"
    assert page.task_table.item(0, 6).text() == "待办"
    assert changed

    task_id = page.task_table.item(0, 0).data(Qt.UserRole)
    assert page.select_task(task_id)
    assert page.complete_selected("客户确认收到报价")
    assert page.task_table.item(0, 6).text() == "已完成"
    assert "客户确认收到报价" in page.task_table.item(0, 5).text()
    assert followups.get(task_id).status == "completed"
    page.close()


def test_record_result_and_cancel_from_table(application, database):
    customers, followups = _services(database)
    alice = _customer(customers, "Alice")
    due = datetime.now().astimezone() + timedelta(hours=2)
    first = followups.create(alice.id, due, "资料跟进", "medium", "补充规格书")
    second = followups.create(alice.id, due, "取消跟进", "low", "无需继续")
    page = FollowupPage(followups, customers)
    page.refresh_customers()
    page.refresh()

    assert page.select_task(first.id)
    assert page.record_selected_result("客户表示稍后回复")
    assert followups.get(first.id).status == "pending"
    assert followups.get(first.id).result == "客户表示稍后回复"

    assert page.select_task(second.id)
    assert page.cancel_selected()
    assert followups.get(second.id).status == "cancelled"
    page.close()


def test_filters_customer_and_status_and_marks_overdue(application, database):
    customers, followups = _services(database)
    alice = _customer(customers, "Alice")
    bob = _customer(customers, "Bob")
    now = datetime.now().astimezone()
    overdue = followups.create(
        bob.id, now - timedelta(days=1), "逾期任务", "high", "补发资料"
    )
    pending = followups.create(
        alice.id, now + timedelta(days=1), "待办任务", "medium", "确认样品"
    )
    done = followups.create(
        alice.id, now + timedelta(days=2), "完成任务", "low", "发送目录"
    )
    followups.complete(done.id, "已发送")
    page = FollowupPage(followups, customers)
    page.refresh_customers()
    page.refresh()

    assert page.task_table.rowCount() == 3
    row = page.find_task_row(overdue.id)
    assert page.task_table.item(row, 7).text() == "逾期"

    page.customer_filter_combo.setCurrentIndex(
        page.customer_filter_combo.findData(alice.id)
    )
    page.refresh()
    assert page.task_table.rowCount() == 2
    assert pending.id in {
        page.task_table.item(index, 0).data(Qt.UserRole)
        for index in range(page.task_table.rowCount())
    }

    page.status_filter_combo.setCurrentIndex(
        page.status_filter_combo.findData("completed")
    )
    page.refresh()
    assert page.task_table.rowCount() == 1
    assert page.task_table.item(0, 6).text() == "已完成"
    page.close()


def test_ai_prefill_requires_manual_creation(application, database):
    customers, followups = _services(database)
    alice = _customer(customers, "Alice")
    page = FollowupPage(followups, customers)
    page.refresh_customers()

    page.prefill(alice.id, 3, "礼貌确认客户是否收到报价", "AI 建议跟进")

    assert followups.list() == []
    assert page.customer_combo.currentData() == alice.id
    assert page.reason_edit.text() == "AI 建议跟进"
    assert page.content_edit.toPlainText() == "礼貌确认客户是否收到报价"
    assert page.date_edit.date() == QDate.currentDate().addDays(3)
    assert page.create_task()
    task = followups.list()[0]
    assert task.customer_id == alice.id
    assert task.reason == "AI 建议跟进"
    page.close()


def test_analysis_result_exposes_followup_button_only_when_required(application):
    required = payload()
    required.update(
        followup_required=True, followup_suggestion="三天后礼貌跟进", followup_due_days=3
    )
    widget = AnalysisResultWidget()
    widget.set_analysis(parse_analysis_json(json.dumps(required, ensure_ascii=False)))
    emitted = []
    widget.followup_requested.connect(lambda: emitted.append(True))

    assert widget.followup_button.isVisibleTo(widget)
    widget.followup_button.click()
    assert emitted == [True]

    not_required = payload()
    not_required.update(followup_required=False)
    widget.set_analysis(
        parse_analysis_json(json.dumps(not_required, ensure_ascii=False))
    )
    assert not widget.followup_button.isVisibleTo(widget)
    widget.close()


def test_main_window_uses_followup_page_and_local_reminder(
    application, database, tmp_path, monkeypatch
):
    monkeypatch.setenv("SALESPILOT_DATA_DIR", str(tmp_path))
    window = MainWindow(database)
    try:
        assert isinstance(window.followup_page, FollowupPage)
        assert window.pages.widget(5) is window.followup_page
        version = window.findChild(QLabel, "sidebarVersion")
        assert "阶段 9" in version.text()

        overdue = window.followup_service.create(
            window.customer_service.create({"name": "Alice"}).id,
            datetime.now().astimezone() - timedelta(hours=2),
            "逾期提醒",
            "high",
            "确认客户是否收到资料",
        )
        window.check_followup_reminders()
        assert "逾期" in window.reminder_text

        window.followup_service.complete(overdue.id, "已电话确认")
        window.check_followup_reminders()
        assert window.reminder_text == ""
    finally:
        window.close()


def test_main_window_prefills_followup_from_ai_suggestion(
    application, database, tmp_path, monkeypatch
):
    monkeypatch.setenv("SALESPILOT_DATA_DIR", str(tmp_path))
    window = MainWindow(database)
    try:
        alice = window.customer_service.create({"name": "Alice"})
        window._open_followup_suggestion(
            alice.id,
            {
                "due_days": 3,
                "reason": "AI 建议跟进",
                "content": "礼貌确认客户是否需要补充资料",
            },
        )
        assert window.navigation.currentRow() == 5
        assert window.followup_page.customer_combo.currentData() == alice.id
        assert window.followup_page.content_edit.toPlainText() == "礼貌确认客户是否需要补充资料"
        assert window.followup_service.list() == []
    finally:
        window.close()
