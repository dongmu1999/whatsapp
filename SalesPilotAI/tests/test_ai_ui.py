from __future__ import annotations

import json
import threading
import time

from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QLabel, QMessageBox

from app.database.repositories.analysis_repository import (
    AnalysisRepository,
    APIUsageRepository,
)
from app.database.repositories.customer_repository import CustomerRepository
from app.database.repositories.history_repository import HistoryRepository
from app.database.repositories.memory_repository import MemoryRepository
from app.database.repositories.settings_repository import SettingsRepository
from app.models.analysis import AnalysisParseError, SalesAnalysis
from app.services.ai_settings_service import AISettingsService
from app.services.conversation_service import ConversationService
from app.services.customer_service import CustomerService
from app.services.deepseek_service import ConnectionTestResult, DeepSeekAPIError
from app.services.sales_advisor_service import AnalysisRunResult
from app.services.memory_service import MemoryService
from app.ui.ai_settings_page import AISettingsPage
from app.ui.analysis_result import AnalysisResultWidget
from app.ui.chat_analysis_page import ChatAnalysisPage
from app.ui.main_window import MainWindow
from test_analysis import payload, stats


def _wait_for_signal(application, spy):
    deadline = time.monotonic() + 3
    while spy.count() == 0 and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(0.01)
    application.processEvents()
    assert spy.count() > 0


class FakeCredentials:
    def __init__(self):
        self.value = ""

    def get_api_key(self):
        return self.value

    def set_api_key(self, value):
        self.value = value

    def delete_api_key(self):
        self.value = ""


class FakeConnectionClient:
    def __init__(self, outcome=None):
        self.settings_service = None
        self.outcome = outcome
        self.thread_ids = []

    def test_connection(self):
        self.thread_ids.append(threading.get_ident())
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def test_ai_settings_page_saves_configuration_without_exposing_key(
    application, database
):
    credentials = FakeCredentials()
    service = AISettingsService(SettingsRepository(database), credentials)
    page = AISettingsPage(
        service, FakeConnectionClient(), APIUsageRepository(database)
    )
    page.api_key_edit.setText("sk-ui-secret")
    page.base_url_edit.setText("https://example.invalid/v1/")
    page.model_edit.setText("custom-model")
    page.advanced_model_edit.setText("custom-advanced")
    page.temperature_spin.setValue(0.4)
    page.max_tokens_spin.setValue(2500)
    page.timeout_spin.setValue(45)

    assert page.save_settings()
    assert credentials.value == "sk-ui-secret"
    assert page.api_key_edit.text() == ""
    assert service.load().base_url == "https://example.invalid/v1"
    assert service.load().model == "custom-model"
    assert service.load().advanced_model == "custom-advanced"
    assert service.load().temperature == 0.4
    assert service.load().max_tokens == 2500
    assert service.load().timeout == 45
    page.close()


def test_analysis_result_displays_three_replies_and_copies_edited_english(application):
    widget = AnalysisResultWidget()
    widget.set_analysis(SalesAnalysis.model_validate(payload()))
    widget.reply_cards["professional"].english_edit.setPlainText("Edited reply")

    widget.copy_reply("professional")

    assert application.clipboard().text() == "Edited reply"
    assert len(widget.reply_cards) == 3
    assert widget.score_label.text() == "68 / 100"
    widget.close()


def test_main_window_integrates_phase_four_pages(
    application, database, tmp_path, monkeypatch
):
    monkeypatch.setenv("SALESPILOT_DATA_DIR", str(tmp_path))
    window = MainWindow(database)
    try:
        assert isinstance(window.ai_settings_page, AISettingsPage)
        assert window.pages.widget(6) is window.ai_settings_page
        assert window.chat_analysis_page.analysis_service is not None
        version = window.findChild(QLabel, "sidebarVersion")
        assert "阶段 7" in version.text()
    finally:
        window.close()


def test_ai_settings_connection_uses_worker_and_records_usage(application, database):
    service = AISettingsService(SettingsRepository(database), FakeCredentials())
    client = FakeConnectionClient(ConnectionTestResult("连接成功", stats()))
    page = AISettingsPage(service, client, APIUsageRepository(database))
    finished = QSignalSpy(page.connection_finished)

    page.test_connection()

    _wait_for_signal(application, finished)
    application.processEvents()
    assert client.thread_ids[0] != threading.get_ident()
    assert "连接成功" in page.status_label.text()
    assert "30" in page.usage_label.text()
    usage = database.connection.execute("SELECT * FROM api_usage").fetchone()
    assert usage["total_tokens"] == 30
    assert page.test_button.isEnabled()
    page.close()


def test_ai_settings_clear_key_and_failed_connection_status(application, database):
    credentials = FakeCredentials()
    service = AISettingsService(SettingsRepository(database), credentials)
    failed_stats = stats()
    failed_stats.status = "failed"
    failed_stats.error_type = "timeout"
    client = FakeConnectionClient(
        DeepSeekAPIError("DeepSeek 请求超时，请检查网络。", "timeout", failed_stats)
    )
    page = AISettingsPage(service, client, APIUsageRepository(database))
    page.api_key_edit.setText("sk-to-clear")
    assert page.save_settings()
    assert page.clear_api_key()
    assert credentials.value == ""

    finished = QSignalSpy(page.connection_finished)
    page.test_connection()
    _wait_for_signal(application, finished)
    application.processEvents()

    assert "超时" in page.status_label.text()
    usage = database.connection.execute("SELECT * FROM api_usage").fetchone()
    assert usage["status"] == "failed"
    assert usage["error_type"] == "timeout"
    page.close()


class FakeAdvisor:
    def __init__(self, outcome=None, analysis_data=None):
        self.outcome = outcome
        self.analysis_data = analysis_data or payload()
        self.calls = []
        self.thread_ids = []

    def analyze(self, customer_id, conversation_id, messages, **options):
        self.thread_ids.append(threading.get_ident())
        self.calls.append((customer_id, conversation_id, messages, options))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return AnalysisRunResult(
            customer_id=customer_id,
            conversation_id=conversation_id,
            analysis=SalesAnalysis.model_validate(self.analysis_data),
            raw_response=json.dumps(self.analysis_data),
            api_calls=[stats()],
        )


def _make_analysis_page(database, advisor, knowledge_service=None):
    customer_service = CustomerService(CustomerRepository(database))
    settings_service = AISettingsService(
        SettingsRepository(database), FakeCredentials()
    )
    page = ChatAnalysisPage(
        ConversationService(database),
        customer_service,
        SettingsRepository(database),
        analysis_service=advisor,
        analysis_repository=AnalysisRepository(database),
        usage_repository=APIUsageRepository(database),
        ai_settings_service=settings_service,
        memory_service=MemoryService(
            MemoryRepository(database), HistoryRepository(database)
        ),
        knowledge_service=knowledge_service,
    )
    customer = customer_service.create({"name": "Alice", "company_name": "ACME GmbH"})
    page.refresh_customers()
    page.customer_combo.setCurrentIndex(page.customer_combo.findData(customer.id))
    page.raw_edit.setPlainText("Alice: Need 500 units\nMe: I will confirm")
    page.parse_preview()
    return page, customer


def test_analysis_requires_explicit_upload_confirmation_and_cancel_is_local_only(
    application, database, monkeypatch
):
    advisor = FakeAdvisor()
    page, _ = _make_analysis_page(database, advisor)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.No,
    )

    assert not page.start_analysis()

    assert advisor.calls == []
    assert database.connection.execute(
        "SELECT COUNT(*) FROM conversations"
    ).fetchone()[0] == 0
    assert database.connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0] == 0
    assert "已取消" in page.status_label.text()
    page.close()


def test_analysis_confirmation_success_persists_and_reuses_conversation(
    application, database, monkeypatch
):
    advisor = FakeAdvisor()
    page, customer = _make_analysis_page(database, advisor)
    confirmations = []

    def confirm(*args, **kwargs):
        confirmations.append(args[2])
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", confirm)
    completed = QSignalSpy(page.analysis_completed)

    assert page.start_analysis()
    _wait_for_signal(application, completed)
    application.processEvents()

    assert "2 条消息" in confirmations[0]
    assert "https://api.deepseek.com" in confirmations[0]
    assert "deepseek-flash" in confirmations[0]
    assert "已启用" in confirmations[0]
    assert advisor.thread_ids[0] != threading.get_ident()
    assert advisor.calls[0][0] == customer.id
    assert advisor.calls[0][3]["redact"] is True
    assert page.analysis_result.score_label.text() == "68 / 100"
    assert database.connection.execute(
        "SELECT status FROM analyses"
    ).fetchone()[0] == "completed"
    assert database.connection.execute(
        "SELECT COUNT(*) FROM reply_suggestions"
    ).fetchone()[0] == 3
    assert database.connection.execute("SELECT COUNT(*) FROM api_usage").fetchone()[0] == 1

    second_completed = QSignalSpy(page.analysis_completed)
    assert page.start_analysis()
    _wait_for_signal(application, second_completed)
    application.processEvents()
    assert database.connection.execute(
        "SELECT COUNT(*) FROM conversations"
    ).fetchone()[0] == 1
    assert database.connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0] == 2
    assert advisor.calls[0][1] == advisor.calls[1][1]
    page.close()


def test_analysis_saves_memory_suggestions_as_pending(application, database, monkeypatch):
    class MemoryAdvisor(FakeAdvisor):
        def analyze(self, customer_id, conversation_id, messages, **options):
            base = super().analyze(customer_id, conversation_id, messages, **options)
            data = payload()
            data["memory_suggestions"] = [
                {
                    "category": "purchase_plan",
                    "content": "计划本季度采购 500 件",
                    "evidence": "客户消息提到 500 units",
                }
            ]
            return AnalysisRunResult(
                customer_id=base.customer_id,
                conversation_id=base.conversation_id,
                analysis=SalesAnalysis.model_validate(data),
                raw_response=json.dumps(data),
                api_calls=base.api_calls,
            )

    page, customer = _make_analysis_page(database, MemoryAdvisor())
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes
    )
    completed = QSignalSpy(page.analysis_completed)

    assert page.start_analysis()
    _wait_for_signal(application, completed)
    application.processEvents()

    row = database.connection.execute(
        "SELECT customer_id, category, content, source, status FROM customer_memories"
    ).fetchone()
    assert tuple(row) == (
        customer.id,
        "purchase_plan",
        "计划本季度采购 500 件",
        "ai_suggested",
        "pending",
    )
    page.close()


def test_analysis_followup_suggestion_requires_manual_task_creation(
    application, database, monkeypatch
):
    data = payload()
    data.update(
        followup_required=True,
        followup_suggestion="三天后礼貌确认客户是否收到报价",
        followup_due_days=3,
    )
    page, customer = _make_analysis_page(database, FakeAdvisor(analysis_data=data))
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes
    )
    completed = QSignalSpy(page.analysis_completed)
    captured = []
    page.followup_suggested.connect(
        lambda customer_id, suggestion: captured.append((customer_id, suggestion))
    )

    assert page.start_analysis()
    _wait_for_signal(application, completed)
    application.processEvents()
    assert database.connection.execute("SELECT COUNT(*) FROM followups").fetchone()[0] == 0

    assert page.analysis_result.followup_button.isVisibleTo(page.analysis_result)
    page.analysis_result.followup_button.click()
    application.processEvents()

    assert captured[0][0] == customer.id
    assert captured[0][1]["due_days"] == 3
    assert captured[0][1]["content"] == "三天后礼貌确认客户是否收到报价"
    assert database.connection.execute("SELECT COUNT(*) FROM followups").fetchone()[0] == 0
    page.close()


def test_analysis_failure_preserves_raw_response_and_records_usage(
    application, database, monkeypatch
):
    error = AnalysisParseError("AI 返回的 JSON 格式无效", "invalid raw")
    error.api_calls = [stats()]
    advisor = FakeAdvisor(error)
    page, _ = _make_analysis_page(database, advisor)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    failed = QSignalSpy(page.analysis_failed)

    assert page.start_analysis()
    _wait_for_signal(application, failed)
    application.processEvents()

    row = database.connection.execute(
        "SELECT status, raw_response, error_message FROM analyses"
    ).fetchone()
    assert tuple(row) == ("failed", "invalid raw", "AI 返回的 JSON 格式无效")
    assert database.connection.execute("SELECT COUNT(*) FROM api_usage").fetchone()[0] == 1
    assert "JSON" in page.status_label.text()
    assert page.analyze_button.isEnabled()
    page.close()
