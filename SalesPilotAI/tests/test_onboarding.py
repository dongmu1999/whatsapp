from __future__ import annotations

from app.database.repositories.settings_repository import SettingsRepository
from app.ui.main_window import MainWindow


def test_first_run_guide_links_to_ai_settings_and_remembers_completion(
    application, database, tmp_path, monkeypatch
):
    monkeypatch.setenv("SALESPILOT_DATA_DIR", str(tmp_path))
    window = MainWindow(database)

    try:
        window.show_first_run_guide()
        application.processEvents()
        dialog = window.onboarding_dialog
        assert dialog is not None
        assert dialog.isVisible()
        assert "DeepSeek" in dialog.steps_label.text()
        assert "Ctrl+Shift+A" in dialog.steps_label.text()
        assert "本地" in dialog.steps_label.text()

        dialog.start_button.click()
        application.processEvents()

        assert window.navigation.currentRow() == 6
        assert SettingsRepository(database).get("onboarding_completed") == "1"

        window.show_first_run_guide()
        assert window.onboarding_dialog is None
    finally:
        window.close()


def test_first_run_guide_remains_available_after_later_click(
    application, database, tmp_path, monkeypatch
):
    monkeypatch.setenv("SALESPILOT_DATA_DIR", str(tmp_path))
    window = MainWindow(database)

    try:
        window.show_first_run_guide()
        application.processEvents()
        assert window.onboarding_dialog is not None
        window.onboarding_dialog.later_button.click()
        application.processEvents()

        assert SettingsRepository(database).get("onboarding_completed") is None

        window.show_first_run_guide()
        application.processEvents()
        assert window.onboarding_dialog is not None
        assert window.onboarding_dialog.isVisible()
        window.onboarding_dialog.reject()
    finally:
        window.close()
