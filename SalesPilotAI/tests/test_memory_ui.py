from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.database.repositories.customer_repository import CustomerRepository
from app.database.repositories.history_repository import HistoryRepository
from app.database.repositories.memory_repository import MemoryRepository
from app.models.memory import MemorySuggestion
from app.models.message import CapturedMessage
from app.services.conversation_service import ConversationService
from app.services.customer_service import CustomerService
from app.services.memory_service import MemoryService
from app.ui.customer_history_page import CustomerHistoryPage
from app.ui.main_window import MainWindow


def _build_page(database):
    customer_service = CustomerService(CustomerRepository(database))
    memory_service = MemoryService(MemoryRepository(database), HistoryRepository(database))
    page = CustomerHistoryPage(customer_service, memory_service)
    alice = customer_service.create({"name": "Alice", "company_name": "ACME"})
    customer_service.create({"name": "Bob"})
    page.refresh_customers()
    page.customer_combo.setCurrentIndex(page.customer_combo.findData(alice.id))
    return page, memory_service, alice


def test_customer_history_page_adds_confirms_and_deletes_memory(application, database):
    page, memory_service, alice = _build_page(database)

    page.memory_category_combo.setCurrentIndex(
        page.memory_category_combo.findData("target_price")
    )
    page.memory_content_edit.setText("目标价 12 美元/件")
    assert page.add_memory()

    assert page.memory_table.rowCount() == 1
    assert "12 美元" in page.memory_summary_label.text()

    memory_id = memory_service.list_memories(alice.id)[0].id
    memory_service.record_suggestions(
        alice.id,
        [MemorySuggestion(category="purchase_plan", content="计划 12 月下单")],
    )
    page.refresh()
    assert page.suggestion_table.rowCount() == 1

    page.suggestion_table.selectRow(0)
    assert page.confirm_selected_suggestion()
    assert page.suggestion_table.rowCount() == 0
    assert "计划 12 月下单" in page.memory_summary_label.text()

    for row in range(page.memory_table.rowCount()):
        if page.memory_table.item(row, 0).data(Qt.UserRole) == memory_id:
            page.memory_table.selectRow(row)
            break
    assert page.delete_selected_memory()
    assert memory_id not in [item.id for item in memory_service.list_memories(alice.id)]
    page.close()


def test_customer_history_page_rejects_suggestion_and_searches_only_their_history(
    application, database
):
    page, memory_service, alice = _build_page(database)
    memory_service.record_suggestions(
        alice.id,
        [MemorySuggestion(category="price_sensitivity", content="客户对价格敏感")],
    )
    ConversationService(database).save_capture(
        alice.id,
        "Alice 报价",
        [
            CapturedMessage(
                sender_type="customer", content="Could you share MOQ 500 price?", source="manual"
            )
        ],
    )
    page.refresh()

    page.suggestion_table.selectRow(0)
    assert page.reject_selected_suggestion()
    assert memory_service.summary(alice.id) == ""

    page.history_search_edit.setText("MOQ 500")
    assert page.search_history()
    assert page.history_table.rowCount() == 1
    assert "MOQ 500" in page.history_detail.toPlainText()
    page.close()


def test_main_window_uses_stage_five_history_page(application, database, tmp_path, monkeypatch):
    monkeypatch.setenv("SALESPILOT_DATA_DIR", str(tmp_path))
    window = MainWindow(database)
    try:
        assert isinstance(window.customer_history_page, CustomerHistoryPage)
        assert window.pages.widget(3) is window.customer_history_page
        version = window.findChild(QLabel, "sidebarVersion")
        assert "阶段 8" in version.text()
    finally:
        window.close()
