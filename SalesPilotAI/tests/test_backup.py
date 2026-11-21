from __future__ import annotations

import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from app.config import APP_VERSION
from app.database import Database
from app.database.migrations import MIGRATIONS
from app.services.backup_service import BackupError, BackupService

LATEST_SCHEMA = max(migration.version for migration in MIGRATIONS)


def _insert_customer(database: Database, name: str) -> int:
    cursor = database.connection.execute(
        "INSERT INTO customers(name, country) VALUES (?, 'Germany')", (name,)
    )
    return int(cursor.lastrowid)


def _customers(database: Database) -> list[str]:
    return [
        row["name"]
        for row in database.connection.execute(
            "SELECT name FROM customers ORDER BY name"
        ).fetchall()
    ]


def _manifest(archive: Path) -> dict:
    with zipfile.ZipFile(archive) as bundle:
        return json.loads(bundle.read("manifest.json").decode("utf-8"))


def _database_names(archive: Path, tmp_path: Path) -> list[str]:
    target = tmp_path / "inspect.db"
    with zipfile.ZipFile(archive) as bundle:
        target.write_bytes(bundle.read("salespilot.db"))
    connection = sqlite3.connect(target)
    try:
        return [row[0] for row in connection.execute("SELECT name FROM customers")]
    finally:
        connection.close()
        target.unlink(missing_ok=True)


def _file_database(tmp_path: Path, data_dir: Path) -> Database:
    database = Database(data_dir / "salespilot.db")
    database.initialize()
    return database


def test_backup_contains_manifest_database_and_knowledge(tmp_path):
    data_dir = tmp_path / "data"
    knowledge = data_dir / "knowledge"
    knowledge.mkdir(parents=True)
    (knowledge / "policy.txt").write_text("保修两年", encoding="utf-8")
    database = _file_database(tmp_path, data_dir)
    _insert_customer(database, "Alice")
    service = BackupService(database, data_dir)

    try:
        info = service.create_backup()

        assert info.path.is_file()
        assert info.path.name.startswith("salespilot-backup-")
        assert info.path.suffix == ".zip"
        assert info.knowledge_files == 1
        assert info.database_size > 0
        assert info.schema_version == LATEST_SCHEMA
        assert info.app_version == APP_VERSION

        with zipfile.ZipFile(info.path) as bundle:
            names = set(bundle.namelist())
        assert {"manifest.json", "salespilot.db", "knowledge/policy.txt"} <= names

        manifest = _manifest(info.path)
        assert manifest["format_version"] == 1
        assert manifest["app_version"] == APP_VERSION
        assert manifest["schema_version"] == LATEST_SCHEMA
        assert manifest["knowledge"]["files"] == 1
        assert len(manifest["database"]["sha256"]) == 64
        assert manifest["database"]["sha256"] == hashlib.sha256(
            zipfile.ZipFile(info.path).read("salespilot.db")
        ).hexdigest()
        assert _database_names(info.path, tmp_path) == ["Alice"]
    finally:
        database.close()


def test_backup_uses_configured_directory_and_unique_names(tmp_path):
    data_dir = tmp_path / "data"
    database = _file_database(tmp_path, data_dir)
    service = BackupService(database, data_dir)
    custom = tmp_path / "custom-backups"
    service.set_backup_dir(custom)

    try:
        first = service.create_backup()
        second = service.create_backup()

        assert first.path.parent == custom
        assert second.path.parent == custom
        assert first.path != second.path
        assert service.backup_dir == custom
    finally:
        database.close()


def test_restore_replaces_database_and_knowledge(tmp_path):
    source_dir = tmp_path / "source"
    (source_dir / "knowledge").mkdir(parents=True)
    (source_dir / "knowledge" / "old.txt").write_text("旧资料", encoding="utf-8")
    source = _file_database(tmp_path, source_dir)
    _insert_customer(source, "Alice")
    source_service = BackupService(source, source_dir)
    info = source_service.create_backup()
    source.close()

    target_dir = tmp_path / "target"
    (target_dir / "knowledge").mkdir(parents=True)
    (target_dir / "knowledge" / "new.txt").write_text("新资料", encoding="utf-8")
    target = _file_database(tmp_path, target_dir)
    _insert_customer(target, "Bob")
    target_service = BackupService(target, target_dir)

    try:
        result = target_service.restore_backup(info.path)

        assert result.schema_version == LATEST_SCHEMA
        assert result.safety_backup.is_file()
        assert _customers(target) == ["Alice"]
        knowledge_files = sorted(
            path.name for path in (target_dir / "knowledge").iterdir()
        )
        assert knowledge_files == ["old.txt"]
        assert (target_dir / "knowledge" / "old.txt").read_text(
            encoding="utf-8"
        ) == "旧资料"
        assert _database_names(result.safety_backup, tmp_path) == ["Bob"]
        # 恢复后同一个 Database 对象仍可继续查询和写入。
        assert target.connection.execute(
            "SELECT count(*) FROM database_migrations"
        ).fetchone()[0] == len(MIGRATIONS)
    finally:
        target.close()


def test_restore_rejects_unsafe_archive_paths(tmp_path):
    data_dir = tmp_path / "data"
    database = _file_database(tmp_path, data_dir)
    service = BackupService(database, data_dir)
    valid = service.create_backup()
    archive = tmp_path / "unsafe.zip"

    try:
        with zipfile.ZipFile(valid.path) as source, zipfile.ZipFile(
            archive, "w"
        ) as target:
            for item in source.infolist():
                target.writestr(item, source.read(item.filename))
            target.writestr("../evil.txt", "bad")

        with pytest.raises(BackupError) as error:
            service.restore_backup(archive)
        assert "路径" in str(error.value)
        assert _customers(database) == []
    finally:
        database.close()


def test_restore_rejects_absolute_archive_paths(tmp_path):
    data_dir = tmp_path / "data"
    database = _file_database(tmp_path, data_dir)
    service = BackupService(database, data_dir)
    valid = service.create_backup()
    archive = tmp_path / "absolute.zip"

    try:
        with zipfile.ZipFile(valid.path) as source, zipfile.ZipFile(
            archive, "w"
        ) as target:
            for item in source.infolist():
                target.writestr(item, source.read(item.filename))
            target.writestr("/tmp/evil.txt", "bad")

        with pytest.raises(BackupError) as error:
            service.restore_backup(archive)
        assert "路径" in str(error.value)
    finally:
        database.close()


def test_restore_rejects_missing_manifest_and_invalid_zip(tmp_path):
    data_dir = tmp_path / "data"
    database = _file_database(tmp_path, data_dir)
    service = BackupService(database, data_dir)
    missing = tmp_path / "missing.zip"
    invalid = tmp_path / "invalid.zip"

    try:
        with zipfile.ZipFile(missing, "w") as bundle:
            bundle.writestr("salespilot.db", b"not-a-database")
        invalid.write_text("这不是 ZIP", encoding="utf-8")

        with pytest.raises(BackupError) as missing_error:
            service.restore_backup(missing)
        assert "manifest" in str(missing_error.value)

        with pytest.raises(BackupError) as invalid_error:
            service.restore_backup(invalid)
        assert "ZIP" in str(invalid_error.value)
    finally:
        database.close()


def test_restore_rejects_database_hash_mismatch(tmp_path):
    data_dir = tmp_path / "data"
    database = _file_database(tmp_path, data_dir)
    _insert_customer(database, "Alice")
    service = BackupService(database, data_dir)
    valid = service.create_backup()
    archive = tmp_path / "corrupted.zip"

    try:
        with zipfile.ZipFile(valid.path) as source, zipfile.ZipFile(
            archive, "w"
        ) as target:
            for item in source.infolist():
                data = source.read(item.filename)
                if item.filename == "salespilot.db":
                    data = b"corrupted-database-bytes"
                target.writestr(item, data)

        with pytest.raises(BackupError) as error:
            service.restore_backup(archive)
        assert "校验" in str(error.value)
        assert _customers(database) == ["Alice"]
    finally:
        database.close()


def test_restore_rejects_newer_schema_version(tmp_path):
    data_dir = tmp_path / "data"
    database = _file_database(tmp_path, data_dir)
    service = BackupService(database, data_dir)
    valid = service.create_backup()
    archive = tmp_path / "newer.zip"

    try:
        manifest = _manifest(valid.path)
        manifest["schema_version"] = LATEST_SCHEMA + 1
        with zipfile.ZipFile(valid.path) as source, zipfile.ZipFile(
            archive, "w"
        ) as target:
            for item in source.infolist():
                data = source.read(item.filename)
                if item.filename == "manifest.json":
                    data = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
                target.writestr(item, data)

        with pytest.raises(BackupError) as error:
            service.restore_backup(archive)
        assert "版本" in str(error.value)
    finally:
        database.close()


def test_backup_and_restore_support_memory_database(tmp_path):
    data_dir = tmp_path / "data"
    knowledge = data_dir / "knowledge"
    knowledge.mkdir(parents=True)
    database = Database(":memory:")
    database.initialize()
    _insert_customer(database, "Alice")
    service = BackupService(database, data_dir)
    info = service.create_backup()

    try:
        _insert_customer(database, "Bob")
        (knowledge / "new.txt").write_text("新资料", encoding="utf-8")

        result = service.restore_backup(info.path)

        assert _customers(database) == ["Alice"]
        assert list(knowledge.iterdir()) == []
        assert result.safety_backup.is_file()
    finally:
        database.close()


def test_database_reconnect_keeps_the_same_object(tmp_path):
    database = Database(tmp_path / "salespilot.db")
    database.initialize()
    database.reconnect()

    try:
        assert database.connection.execute("SELECT 1").fetchone()[0] == 1
        database.connection.execute("INSERT INTO customers(name) VALUES ('Alice')")
        assert _customers(database) == ["Alice"]
    finally:
        database.close()
