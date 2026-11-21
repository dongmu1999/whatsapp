from __future__ import annotations

import pytest

from PySide6.QtWidgets import QLabel, QPushButton

from app.ui.main_window import MainWindow
from app.ui.theme import DARK_THEME, LIGHT_THEME


@pytest.fixture
def window(application, database, tmp_path, monkeypatch):
    monkeypatch.setenv("SALESPILOT_DATA_DIR", str(tmp_path))
    main_window = MainWindow(database)
    yield main_window
    main_window.close()


def test_eight_navigation_pages_are_wired(window, application):
    assert window.navigation.count() == 8
    assert window.pages.count() == 8

    for index, title in enumerate(window.NAVIGATION):
        window.navigation.setCurrentRow(index)
        application.processEvents()
        assert window.pages.currentIndex() == index
        assert window.topbar_title.text() == title


def test_quick_start_navigates_to_chat_analysis(window):
    button = window.dashboard.findChild(QPushButton, "primaryButton")
    assert button is not None
    button.click()
    assert window.navigation.currentRow() == 1
    assert window.pages.currentIndex() == 1


def test_theme_switch_and_database_persistence(window, database, application):
    window.set_theme(DARK_THEME)
    application.processEvents()
    assert application.property("theme") == DARK_THEME
    assert window.settings.get("theme") == DARK_THEME
    assert window.settings_page.theme_combo.currentData() == DARK_THEME

    second_window = MainWindow(database)
    try:
        assert second_window.current_theme == DARK_THEME
        second_window.toggle_theme()
        assert application.property("theme") == LIGHT_THEME
        assert database.connection.execute(
            "SELECT value FROM settings WHERE key = 'theme'"
        ).fetchone()[0] == LIGHT_THEME
    finally:
        second_window.close()


def test_dashboard_displays_database_values_and_empty_states(window, database):
    for key in (
        "total_customers",
        "today_analyses",
        "high_intent_customers",
        "pending_followup_customers",
    ):
        assert window.dashboard.cards[key].value_label.text() == "0"
    assert window.dashboard.analysis_card.table.rowCount() == 0

    customer_id = database.connection.execute(
        """
        INSERT INTO customers(name, country, sales_stage, intent_score)
        VALUES ('Real Customer', 'Germany', 'Inquiry', 82)
        """
    ).lastrowid
    database.connection.execute(
        """
        INSERT INTO analyses(customer_id, status, customer_intent, purchase_intent_score)
        VALUES (?, 'completed', '询价', 82)
        """,
        (customer_id,),
    )
    window.dashboard.refresh()

    assert window.dashboard.cards["total_customers"].value_label.text() == "1"
    assert window.dashboard.cards["today_analyses"].value_label.text() == "1"
    assert window.dashboard.cards["high_intent_customers"].value_label.text() == "1"
    assert window.dashboard.analysis_card.table.rowCount() == 1
    assert window.dashboard.analysis_card.table.item(0, 0).text() == "Real Customer"


def test_window_supports_target_resolution(window, application):
    window.resize(1366, 768)
    window.show()
    application.processEvents()
    assert window.width() == 1366
    assert window.height() == 768
    assert window.dashboard.isVisible()
