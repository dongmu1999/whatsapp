from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QLabel

from app.database.repositories.settings_repository import SettingsRepository
from app.services.backup_service import BackupService
from app.services.data_maintenance_service import DataMaintenanceService
from app.ui.main_window import MainWindow
from app.ui.settings_page import SettingsPage
from app.ui.theme import LIGHT_THEME


@pytest.fixture
def services(database, tmp_path):
    settings = SettingsRepository(database)
    data_dir = tmp_path / "data"
    (data_dir / "knowledge").mkdir(parents=True)
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    backup = BackupService(database, data_dir, settings=settings)
    maintenance = DataMaintenanceService(
        database, data_dir, settings=settings, temp_dir=temp_dir
    )
    return settings, data_dir, temp_dir, backup, maintenance


@pytest.fixture
def page(application, services):
    settings, data_dir, _, backup, maintenance = services
    widget = SettingsPage(
        LIGHT_THEME,
        data_dir,
        backup_service=backup,
        maintenance_service=maintenance,
        settings_repository=settings,
    )
    yield widget
    widget.close()


def _add_customer(database, name: str) -> int:
    return int(
        database.connection.execute(
            "INSERT INTO customers(name) VALUES (?)", (name,)
        ).lastrowid
    )


def test_settings_page_exposes_backup_and_privacy_controls(page, services):
    _, data_dir, _, _, _ = services

    assert page.backup_button.isEnabled()
    assert page.restore_button.isEnabled()
    assert page.backup_dir_edit.text() == str(data_dir / "backups")
    assert page.retention_spin.value() == 0
    assert "阶段 8" in page.version_label.text()


def test_backup_button_creates_archive(page, services):
    _, _, _, backup, _ = services
    _add_customer(backup.database, "Alice")

    assert page.create_backup()

    archives = list(backup.backup_dir.glob("salespilot-backup-*.zip"))
    assert len(archives) == 1
    assert "备份成功" in page.backup_status_label.text()


def test_restore_backup_emits_signal_and_replaces_data(page, services, database):
    _, _, _, backup, _ = services
    _add_customer(database, "Alice")
    info = backup.create_backup()
    _add_customer(database, "Bob")
    restored = []
    page.data_restored.connect(lambda: restored.append(True))

    assert page.restore_backup(info.path, confirm=False)

    assert restored == [True]
    names = [
        row["name"]
        for row in database.connection.execute("SELECT name FROM customers")
    ]
    assert names == ["Alice"]
    assert "恢复完成" in page.backup_status_label.text()


def test_retention_setting_is_saved(page, services):
    settings, _, _, _, maintenance = services
    page.retention_spin.setValue(15)

    assert page.save_retention()

    assert maintenance.get_retention_days() == 15
    assert settings.get("chat_retention_days") == "15"
    assert "保留期限" in page.privacy_status_label.text()


def test_clear_all_data_from_page(page, database):
    _add_customer(database, "Alice")

    assert page.clear_all_data(confirm=False)

    assert database.connection.execute(
        "SELECT count(*) FROM customers"
    ).fetchone()[0] == 0
    assert "已清空" in page.privacy_status_label.text()


def test_clean_screenshots_from_page(page, services):
    _, _, temp_dir, _, _ = services
    old = temp_dir / "salespilot-capture-old.png"
    old.write_bytes(b"png")
    old_time = old.stat().st_mtime - 48 * 3600
    os.utime(old, (old_time, old_time))

    assert page.clean_screenshots()

    assert not old.exists()
    assert "临时截图" in page.privacy_status_label.text()


def test_main_window_wires_stage_eight_services(application, database, tmp_path, monkeypatch):
    monkeypatch.setenv("SALESPILOT_DATA_DIR", str(tmp_path))
    window = MainWindow(database)

    try:
        assert window.settings_page.backup_service is not None
        assert window.settings_page.maintenance_service is not None
        assert "阶段 8" in window.settings_page.version_label.text()
        sidebar_version = window.findChild(QLabel, "sidebarVersion")
        assert sidebar_version is not None
        assert "阶段 8" in sidebar_version.text()
        window.refresh_after_restore()
    finally:
        window.close()


def test_main_window_applies_retention_on_startup(
    application, database, tmp_path, monkeypatch
):
    settings = SettingsRepository(database)
    settings.set("chat_retention_days", "30")
    customer_id = _add_customer(database, "Alice")
    database.connection.execute(
        """
        INSERT INTO conversations(customer_id, last_message_at)
        VALUES (?, '2020-01-01T00:00:00.000Z')
        """,
        (customer_id,),
    )
    monkeypatch.setenv("SALESPILOT_DATA_DIR", str(tmp_path))

    window = MainWindow(database)

    try:
        assert database.connection.execute(
            "SELECT count(*) FROM conversations"
        ).fetchone()[0] == 0
        assert window.settings_page.retention_spin.value() == 30
    finally:
        window.close()
