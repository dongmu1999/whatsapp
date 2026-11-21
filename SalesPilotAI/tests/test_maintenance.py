from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.database import Database
from app.database.repositories.settings_repository import SettingsRepository
from app.services.data_maintenance_service import DataMaintenanceService

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)


def _conversation(
    database: Database,
    *,
    name: str = "Alice",
    last_message_at: str | None,
    created_at: str = "2026-11-20T00:00:00.000Z",
) -> tuple[int, int]:
    customer_id = int(
        database.connection.execute(
            "INSERT INTO customers(name) VALUES (?)", (name,)
        ).lastrowid
    )
    conversation_id = int(
        database.connection.execute(
            """
            INSERT INTO conversations(customer_id, title, last_message_at, created_at)
            VALUES (?, '聊天', ?, ?)
            """,
            (customer_id, last_message_at, created_at),
        ).lastrowid
    )
    return customer_id, conversation_id


def _services(database: Database, data_dir: Path, temp_dir: Path):
    settings = SettingsRepository(database)
    service = DataMaintenanceService(
        database, data_dir, settings=settings, temp_dir=temp_dir
    )
    return settings, service


def test_retention_days_roundtrip_and_validation(tmp_path, database):
    settings, service = _services(
        database, tmp_path / "data", tmp_path / "temp"
    )

    assert service.get_retention_days() == 0
    assert service.set_retention_days(30) == 30
    assert service.get_retention_days() == 30
    assert settings.get("chat_retention_days") == "30"

    with pytest.raises(ValueError):
        service.set_retention_days(-1)
    with pytest.raises(ValueError):
        service.set_retention_days(3651)
    with pytest.raises(ValueError):
        service.set_retention_days("abc")


def test_apply_retention_removes_old_conversations_only(tmp_path, database):
    _, service = _services(database, tmp_path / "data", tmp_path / "temp")
    service.set_retention_days(30)
    _, old_id = _conversation(
        database, name="Old", last_message_at="2020-01-01T00:00:00.000Z"
    )
    _, null_id = _conversation(
        database,
        name="NullTime",
        last_message_at=None,
        created_at="2020-01-01T00:00:00.000Z",
    )
    _, recent_id = _conversation(
        database, name="Recent", last_message_at="2026-11-20T00:00:00.000Z"
    )
    database.connection.execute(
        "INSERT INTO messages(conversation_id, content) VALUES (?, '旧消息')",
        (old_id,),
    )

    deleted = service.apply_retention(now=NOW)

    assert deleted == 2
    remaining = {
        row["id"]
        for row in database.connection.execute("SELECT id FROM conversations")
    }
    assert remaining == {recent_id}
    assert database.connection.execute(
        "SELECT count(*) FROM messages WHERE conversation_id = ?", (old_id,)
    ).fetchone()[0] == 0
    assert database.connection.execute(
        "SELECT count(*) FROM customers"
    ).fetchone()[0] == 3
    assert null_id not in remaining


def test_zero_retention_keeps_all_conversations(tmp_path, database):
    _, service = _services(database, tmp_path / "data", tmp_path / "temp")
    _conversation(database, last_message_at="2000-01-01T00:00:00.000Z")

    assert service.apply_retention(now=NOW) == 0
    assert database.connection.execute(
        "SELECT count(*) FROM conversations"
    ).fetchone()[0] == 1


def test_cleanup_temp_screenshots_only_removes_old_capture_files(tmp_path, database):
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir()
    _, service = _services(database, tmp_path / "data", temp_dir)
    old = temp_dir / "salespilot-capture-old.png"
    fresh = temp_dir / "salespilot-capture-fresh.png"
    unrelated = temp_dir / "other.png"
    for path in (old, fresh, unrelated):
        path.write_bytes(b"png")
    old_time = NOW.timestamp() - 48 * 3600
    os.utime(old, (old_time, old_time))

    removed = service.cleanup_temp_screenshots(now=NOW)

    assert removed == 1
    assert not old.exists()
    assert fresh.exists()
    assert unrelated.exists()


def test_clear_all_data_keeps_settings_and_migrations(tmp_path, database):
    data_dir = tmp_path / "data"
    knowledge = data_dir / "knowledge"
    knowledge.mkdir(parents=True)
    document = knowledge / "policy.txt"
    document.write_text("资料", encoding="utf-8")
    settings, service = _services(database, data_dir, tmp_path / "temp")
    settings.set("theme", "dark")

    customer_id = int(
        database.connection.execute(
            "INSERT INTO customers(name) VALUES ('Alice')"
        ).lastrowid
    )
    conversation_id = int(
        database.connection.execute(
            """
            INSERT INTO conversations(customer_id, last_message_at)
            VALUES (?, '2026-11-20T00:00:00.000Z')
            """,
            (customer_id,),
        ).lastrowid
    )
    database.connection.execute(
        "INSERT INTO messages(conversation_id, content) VALUES (?, 'hello')",
        (conversation_id,),
    )
    analysis_id = int(
        database.connection.execute(
            """
            INSERT INTO analyses(customer_id, conversation_id, status)
            VALUES (?, ?, 'completed')
            """,
            (customer_id, conversation_id),
        ).lastrowid
    )
    database.connection.execute(
        """
        INSERT INTO reply_suggestions(
            analysis_id, type, english, chinese, strategy, use_case
        ) VALUES (?, 'professional', 'Hi', '你好', '策略', '场景')
        """,
        (analysis_id,),
    )
    database.connection.execute(
        """
        INSERT INTO customer_memories(customer_id, category, content)
        VALUES (?, '其他', '记忆')
        """,
        (customer_id,),
    )
    product_id = int(
        database.connection.execute(
            "INSERT INTO products(name) VALUES ('产品')"
        ).lastrowid
    )
    database.connection.execute(
        """
        INSERT INTO knowledge_documents(
            product_id, file_name, file_path, file_type, content, checksum, status
        ) VALUES (?, 'policy.txt', ?, 'text', '资料', 'checksum-1', 'indexed')
        """,
        (product_id, str(document)),
    )
    database.connection.execute(
        """
        INSERT INTO followups(customer_id, due_at, content)
        VALUES (?, '2026-11-22T00:00:00.000Z', '回访')
        """,
        (customer_id,),
    )
    database.connection.execute(
        "INSERT INTO api_usage(model, status) VALUES ('deepseek-flash', 'success')"
    )

    counts = service.clear_all_data()

    for table in (
        "customers",
        "conversations",
        "messages",
        "analyses",
        "reply_suggestions",
        "customer_memories",
        "products",
        "knowledge_documents",
        "followups",
        "api_usage",
    ):
        assert database.connection.execute(
            f"SELECT count(*) FROM {table}"
        ).fetchone()[0] == 0
    assert counts["customers"] == 1
    assert counts["knowledge_files"] == 1
    assert settings.get("theme") == "dark"
    assert database.connection.execute(
        "SELECT count(*) FROM database_migrations"
    ).fetchone()[0] > 0
    assert list(knowledge.iterdir()) == []
