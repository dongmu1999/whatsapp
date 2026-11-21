from __future__ import annotations

from app.config import get_data_dir, get_database_path


def test_data_directory_can_be_isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SALESPILOT_DATA_DIR", str(tmp_path / "isolated"))
    assert get_data_dir() == (tmp_path / "isolated").resolve()
    assert get_database_path() == (tmp_path / "isolated").resolve() / "salespilot.db"
