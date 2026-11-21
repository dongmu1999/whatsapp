from __future__ import annotations

import pytest
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QLabel, QMessageBox

from app.capture.models import CaptureResult
from app.database.repositories.customer_repository import CustomerRepository
from app.database.repositories.settings_repository import SettingsRepository
from app.models.message import CapturedMessage
from app.services.conversation_service import ConversationService
from app.services.customer_service import CustomerService
from app.ui.chat_analysis_page import ChatAnalysisPage
from app.ui.main_window import MainWindow


class StubCaptureService:
    def __init__(self, result=None):
        self.result = result
        self.calls = []

    def capture_current(self, **options):
        self.calls.append(options)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def customer_service(database):
    return CustomerService(CustomerRepository(database))


@pytest.fixture
def page(application, database, customer_service):
    capture = StubCaptureService(
        CaptureResult(
            title="Alice",
            window_title="WhatsApp",
            source="uia",
            messages=[
                CapturedMessage(
                    "Visible customer text",
                    sender_type="customer",
                    source="uia",
                    recognized_at="2026-11-21T08:00:00Z",
                )
            ],
            may_be_incomplete=True,
            warning="仅包含当前可见消息",
        )
    )
    widget = ChatAnalysisPage(
        ConversationService(database),
        customer_service,
        SettingsRepository(database),
        capture,
    )
    yield widget
    widget.close()


def _select_customer(page, customer):
    index = page.customer_combo.findData(customer.id)
    page.customer_combo.setCurrentIndex(index)


def test_manual_paste_parse_preview_edit_sender_and_save(page, database, customer_service):
    customer = customer_service.create({"name": "Alice"})
    page.refresh_customers()
    _select_customer(page, customer)
    page.raw_edit.setPlainText("Alice: Need 500 units\nMe: I will confirm")
    page.title_edit.setText("Alice WhatsApp")

    page.parse_preview()

    assert page.message_table.rowCount() == 2
    assert page.message_table.cellWidget(0, 1).currentData() == "customer"
    assert page.message_table.cellWidget(1, 1).currentData() == "sales"
    page.message_table.item(0, 2).setText("Need 600 units")
    page.message_table.cellWidget(0, 1).setCurrentIndex(
        page.message_table.cellWidget(0, 1).findData("unknown")
    )

    assert page.save_capture()

    row = database.connection.execute(
        "SELECT content, sender_type FROM messages"
    ).fetchone()
    assert tuple(row) == ("Need 600 units", "unknown")
    assert "已保存" in page.status_label.text()


def test_capture_populates_editable_preview_without_saving(page, database):
    page.capture_current_chat()

    assert page.title_edit.text() == "Alice"
    assert page.message_table.rowCount() == 1
    assert page.message_table.item(0, 2).text() == "Visible customer text"
    assert "可能不完整" in page.incomplete_label.text()
    assert database.connection.execute(
        "SELECT COUNT(*) FROM conversations"
    ).fetchone()[0] == 0


def test_capture_requires_customer_before_local_save(page, database):
    page.load_result(
        CaptureResult(
            title="Unknown",
            window_title="WhatsApp",
            source="manual",
            messages=[CapturedMessage("Text")],
            may_be_incomplete=True,
        )
    )

    assert not page.save_capture()
    assert "选择客户" in page.status_label.text()
    assert database.connection.execute(
        "SELECT COUNT(*) FROM conversations"
    ).fetchone()[0] == 0


def test_capture_settings_are_validated_persisted_and_hotkey_emitted(page, database):
    emitted = []
    page.hotkey_changed.connect(emitted.append)
    page.hotkey_edit.setKeySequence(QKeySequence("Ctrl+Shift+B"))
    page.limit_spin.setValue(40)
    page.uia_check.setChecked(False)
    page.ocr_check.setChecked(True)
    page.browser_check.setChecked(True)

    assert page.save_settings()

    settings = SettingsRepository(database)
    assert settings.get("capture_hotkey") == "Ctrl+Shift+B"
    assert settings.get("capture_message_limit") == "40"
    assert settings.get("capture_uia_enabled") == "0"
    assert settings.get("capture_ocr_enabled") == "1"
    assert settings.get("capture_allow_browser") == "1"
    assert emitted == ["Ctrl+Shift+B"]


def test_capture_button_passes_saved_options(page):
    page.limit_spin.setValue(45)
    page.uia_check.setChecked(False)
    page.ocr_check.setChecked(True)
    page.browser_check.setChecked(True)

    page.capture_current_chat()

    assert page.capture_service.calls[-1] == {
        "use_uia": False,
        "use_ocr": True,
        "allow_browser": True,
        "limit": 45,
    }


def test_delete_selected_preview_row(page):
    page.raw_edit.setPlainText("First\nSecond")
    page.parse_preview()
    page.message_table.selectRow(0)

    page.delete_selected_message()

    assert page.message_table.rowCount() == 1
    assert page.message_table.item(0, 2).text() == "Second"


def test_capture_error_is_chinese_and_does_not_clear_existing_preview(
    page, monkeypatch
):
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)
    page.raw_edit.setPlainText("Keep this")
    page.parse_preview()
    page.capture_service.result = RuntimeError("capture failed")

    page.capture_current_chat()

    assert page.message_table.rowCount() == 1
    assert "捕获失败" in page.status_label.text()


def test_main_window_integrates_real_chat_analysis_page(application, database, tmp_path, monkeypatch):
    monkeypatch.setenv("SALESPILOT_DATA_DIR", str(tmp_path))
    window = MainWindow(database)
    try:
        assert isinstance(window.chat_analysis_page, ChatAnalysisPage)
        assert window.pages.widget(1) is window.chat_analysis_page
        version = window.findChild(QLabel, "sidebarVersion")
        assert version is not None
        assert "阶段 3" in version.text()
    finally:
        window.close()
