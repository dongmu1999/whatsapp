from __future__ import annotations

import sqlite3

import pytest

from app.database import Database
from app.database.repositories.dashboard_repository import DashboardRepository
from app.database.repositories.settings_repository import SettingsRepository


REQUIRED_TABLES = {
    "customers",
    "conversations",
    "messages",
    "analyses",
    "reply_suggestions",
    "customer_memories",
    "products",
    "knowledge_documents",
    "followups",
    "settings",
    "api_usage",
    "database_migrations",
    "customer_search",
    "message_search",
    "knowledge_search",
}


def _add_customer(database: Database, name: str, score: int = 0) -> int:
    cursor = database.connection.execute(
        "INSERT INTO customers(name, intent_score) VALUES (?, ?)", (name, score)
    )
    return int(cursor.lastrowid)


def test_initialization_creates_schema_and_is_idempotent():
    database = Database(":memory:")
    try:
        assert database.initialize() == [1, 2]
        assert database.initialize() == []

        tables = {
            row["name"]
            for row in database.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert REQUIRED_TABLES <= tables
        assert database.connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert database.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        migration = database.connection.execute(
            "SELECT version, name FROM database_migrations"
        ).fetchone()
        assert tuple(migration) == (1, "initial_schema")
    finally:
        database.close()


def test_file_database_reopens_with_data_and_wal(tmp_path):
    path = tmp_path / "data" / "salespilot.db"
    database = Database(path)
    database.initialize()
    with database.transaction():
        _add_customer(database, "Persistent Customer")
    database.close()

    reopened = Database(path)
    try:
        assert reopened.initialize() == []
        assert reopened.connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert reopened.connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 1
    finally:
        reopened.close()


def test_transaction_rolls_back_on_error(database):
    with pytest.raises(RuntimeError, match="force rollback"):
        with database.transaction() as connection:
            connection.execute("INSERT INTO customers(name) VALUES ('Rolled Back')")
            raise RuntimeError("force rollback")

    assert database.connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 0


def test_foreign_keys_and_customer_delete_cascade(database):
    customer_id = _add_customer(database, "Cascade Customer")
    conversation_id = database.connection.execute(
        "INSERT INTO conversations(customer_id, title) VALUES (?, ?)",
        (customer_id, "WhatsApp"),
    ).lastrowid
    database.connection.execute(
        "INSERT INTO messages(conversation_id, content, sequence_number) VALUES (?, 'Hello', 1)",
        (conversation_id,),
    )
    analysis_id = database.connection.execute(
        "INSERT INTO analyses(customer_id, conversation_id, status) VALUES (?, ?, 'completed')",
        (customer_id, conversation_id),
    ).lastrowid
    database.connection.execute(
        """
        INSERT INTO reply_suggestions(
            analysis_id, type, english, chinese, strategy, use_case
        ) VALUES (?, 'professional', 'Hello', '你好', '建立信任', '首次联系')
        """,
        (analysis_id,),
    )
    database.connection.execute(
        "INSERT INTO customer_memories(customer_id, category, content) VALUES (?, '背景', '进口商')",
        (customer_id,),
    )
    database.connection.execute(
        "INSERT INTO followups(customer_id, due_at, content) VALUES (?, '2026-11-22T09:00:00Z', '礼貌跟进')",
        (customer_id,),
    )

    with database.transaction() as connection:
        connection.execute("DELETE FROM customers WHERE id = ?", (customer_id,))

    for table in (
        "conversations",
        "messages",
        "analyses",
        "reply_suggestions",
        "customer_memories",
        "followups",
    ):
        assert database.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0

    with pytest.raises(sqlite3.IntegrityError):
        database.connection.execute(
            "INSERT INTO conversations(customer_id) VALUES (999999)"
        )


def test_customer_and_message_fts_stay_synchronized(database):
    customer_id = _add_customer(database, "Alice")
    database.connection.execute(
        "UPDATE customers SET company_name = 'Initial Co' WHERE id = ?", (customer_id,)
    )
    assert database.connection.execute(
        "SELECT rowid FROM customer_search WHERE customer_search MATCH 'Alice'"
    ).fetchone()[0] == customer_id

    database.connection.execute(
        "UPDATE customers SET company_name = 'Globex Trading' WHERE id = ?",
        (customer_id,),
    )
    assert database.connection.execute(
        "SELECT rowid FROM customer_search WHERE customer_search MATCH 'Globex'"
    ).fetchone()[0] == customer_id

    conversation_id = database.connection.execute(
        "INSERT INTO conversations(customer_id) VALUES (?)", (customer_id,)
    ).lastrowid
    message_id = database.connection.execute(
        "INSERT INTO messages(conversation_id, content) VALUES (?, 'Need quotation')",
        (conversation_id,),
    ).lastrowid
    assert database.connection.execute(
        "SELECT rowid FROM message_search WHERE message_search MATCH 'quotation'"
    ).fetchone()[0] == message_id

    database.connection.execute(
        "UPDATE messages SET content = 'Updated delivery request' WHERE id = ?",
        (message_id,),
    )
    assert database.connection.execute(
        "SELECT COUNT(*) FROM message_search WHERE message_search MATCH 'quotation'"
    ).fetchone()[0] == 0
    assert database.connection.execute(
        "SELECT rowid FROM message_search WHERE message_search MATCH 'delivery'"
    ).fetchone()[0] == message_id

    database.connection.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    assert database.connection.execute(
        "SELECT COUNT(*) FROM customer_search WHERE customer_search MATCH 'Globex'"
    ).fetchone()[0] == 0
    assert database.connection.execute(
        "SELECT COUNT(*) FROM message_search WHERE message_search MATCH 'delivery'"
    ).fetchone()[0] == 0


def test_knowledge_fts_and_product_set_null(database):
    product_id = database.connection.execute(
        "INSERT INTO products(name, model) VALUES ('Valve', 'V-100')"
    ).lastrowid
    document_id = database.connection.execute(
        """
        INSERT INTO knowledge_documents(
            product_id, file_name, file_path, file_type, title, content, checksum
        ) VALUES (?, 'valve.txt', '/tmp/valve.txt', 'txt', 'Valve manual', 'MOQ 50 units', 'abc123')
        """,
        (product_id,),
    ).lastrowid
    assert database.connection.execute(
        "SELECT rowid FROM knowledge_search WHERE knowledge_search MATCH 'MOQ'"
    ).fetchone()[0] == document_id

    database.connection.execute("DELETE FROM products WHERE id = ?", (product_id,))
    remaining = database.connection.execute(
        "SELECT product_id FROM knowledge_documents WHERE id = ?", (document_id,)
    ).fetchone()
    assert remaining["product_id"] is None


def test_settings_repository_updates_values(database):
    settings = SettingsRepository(database)
    assert settings.get("theme", "light") == "light"
    settings.set("theme", "dark")
    assert settings.get("theme") == "dark"
    settings.set("theme", "light")
    assert settings.get("theme") == "light"
    assert database.connection.execute(
        "SELECT COUNT(*) FROM settings WHERE key = 'theme'"
    ).fetchone()[0] == 1


def test_dashboard_summary_and_recent_rows_use_real_data(database):
    first = _add_customer(database, "High A", 85)
    second = _add_customer(database, "High B", 70)
    _add_customer(database, "New C", 20)
    for customer_id in (first, second):
        database.connection.execute(
            "INSERT INTO analyses(customer_id, status, customer_intent) VALUES (?, 'completed', '询价')",
            (customer_id,),
        )
    old_analysis = database.connection.execute(
        "INSERT INTO analyses(customer_id, status) VALUES (?, 'completed')", (first,)
    ).lastrowid
    database.connection.execute(
        "UPDATE analyses SET created_at = '2000-01-01T00:00:00Z' WHERE id = ?",
        (old_analysis,),
    )
    database.connection.execute(
        "INSERT INTO followups(customer_id, due_at, content) VALUES (?, '2026-11-22T09:00:00Z', '第一次跟进')",
        (first,),
    )
    database.connection.execute(
        "INSERT INTO followups(customer_id, due_at, content) VALUES (?, '2026-11-23T09:00:00Z', '第二次跟进')",
        (first,),
    )
    database.connection.execute(
        "INSERT INTO followups(customer_id, due_at, content, status) VALUES (?, '2026-11-22T09:00:00Z', '已完成', 'completed')",
        (second,),
    )

    repository = DashboardRepository(database)
    summary = repository.get_summary()
    assert summary.total_customers == 3
    assert summary.today_analyses == 2
    assert summary.high_intent_customers == 2
    assert summary.pending_followup_customers == 1
    assert len(repository.get_recent_analyses()) == 3
    assert len(repository.get_recent_customers()) == 3
    assert len(repository.get_upcoming_followups()) == 2
