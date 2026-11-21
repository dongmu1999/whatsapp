from __future__ import annotations

import pytest

from PySide6.QtWidgets import QDialog, QMessageBox

from app.database.repositories.customer_repository import CustomerRepository
from app.services.customer_service import CustomerService
from app.ui.customer_detail import CustomerDetailDialog, CustomerEditDialog
from app.ui.customer_page import CustomerPage
from app.ui.main_window import MainWindow


@pytest.fixture
def service(database):
    return CustomerService(CustomerRepository(database))


@pytest.fixture
def customer_page(application, service):
    page = CustomerPage(service)
    yield page
    page.close()


def test_customer_page_searches_filters_and_displays_rows(customer_page, service):
    service.create(
        {
            "name": "Alice",
            "company_name": "Globex",
            "country": "Germany",
            "sales_stage": "Inquiry",
            "intent_score": 88,
            "last_contact_at": "2026-11-20T10:00:00Z",
        }
    )
    service.create(
        {
            "name": "Bob",
            "company_name": "Acme",
            "country": "United States",
            "sales_stage": "Interested",
            "intent_score": 35,
        }
    )
    customer_page.refresh()
    assert customer_page.table.rowCount() == 2
    assert "2" in customer_page.count_label.text()

    customer_page.search_edit.setText("Alice")
    assert customer_page.table.rowCount() == 1
    assert customer_page.table.item(0, 0).text() == "Alice"

    customer_page.search_edit.clear()
    customer_page.country_combo.setCurrentIndex(
        customer_page.country_combo.findData("United States")
    )
    assert customer_page.table.rowCount() == 1
    assert customer_page.table.item(0, 0).text() == "Bob"

    customer_page.country_combo.setCurrentIndex(0)
    customer_page.stage_combo.setCurrentIndex(
        customer_page.stage_combo.findData("Inquiry")
    )
    assert customer_page.table.rowCount() == 1
    assert customer_page.table.item(0, 0).text() == "Alice"


def test_customer_edit_dialog_and_detail_cover_customer_fields(service):
    dialog = CustomerEditDialog()
    dialog.fields["name"].setText("UI Customer")
    dialog.fields["company_name"].setText("UI Company")
    dialog.fields["country"].setText("Brazil")
    dialog.fields["intent_score"].setValue(76)
    dialog.fields["notes"].setPlainText("完整客户备注")
    dialog.accept()

    assert dialog.result() == QDialog.Accepted
    customer = service.create(dialog.data())
    assert customer.name == "UI Customer"
    assert customer.intent_score == 76

    detail = CustomerDetailDialog(customer)
    assert detail.field_values["name"].text() == "UI Customer"
    assert detail.field_values["company_name"].text() == "UI Company"
    assert detail.field_values["notes"].text() == "完整客户备注"
    assert detail.field_values["id"].text() == str(customer.id)
    detail.close()
    dialog.close()


def test_customer_page_deletes_after_confirmation(
    customer_page, service, database, monkeypatch
):
    customer = service.create({"name": "Delete Me"})
    database.connection.execute(
        "INSERT INTO conversations(customer_id) VALUES (?)", (customer.id,)
    )
    customer_page.refresh()
    customer_page.table.selectRow(0)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    customer_page.delete_selected()

    assert service.get(customer.id) is None
    assert database.connection.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 0
    assert customer_page.table.rowCount() == 0


def test_main_window_uses_real_customer_page_and_refreshes_dashboard(
    application, database
):
    window = MainWindow(database)
    try:
        assert isinstance(window.pages.widget(2), CustomerPage)
        window.customer_page.service.create(
            {"name": "Integrated", "country": "Germany", "intent_score": 80}
        )
        window.navigation.setCurrentRow(2)
        application.processEvents()
        assert window.customer_page.table.rowCount() == 1

        window.customer_page.customers_changed.emit()
        assert window.dashboard.cards["total_customers"].value_label.text() == "1"
        assert window.dashboard.cards["high_intent_customers"].value_label.text() == "1"
    finally:
        window.close()
