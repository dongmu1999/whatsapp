from __future__ import annotations

import pytest

from app.models.message import CapturedMessage
from app.services.conversation_service import ConversationService, ConversationValidationError


def _customer(database, name="Alice"):
    return database.connection.execute(
        "INSERT INTO customers(name) VALUES (?)", (name,)
    ).lastrowid


def test_save_capture_persists_conversation_messages_metadata_and_fts(database):
    customer_id = _customer(database)
    service = ConversationService(database)
    messages = [
        CapturedMessage(
            "Need quotation for 500 units",
            sender_type="customer",
            timestamp="2026-11-21 10:30",
            source="uia",
            recognized_at="2026-11-21T08:00:00Z",
            confidence=0.95,
        ),
        CapturedMessage(
            "I will confirm the price",
            sender_type="sales",
            timestamp="2026-11-21 10:31",
            source="uia",
            recognized_at="2026-11-21T08:00:01Z",
        ),
    ]

    conversation_id = service.save_capture(
        customer_id, "Alice WhatsApp", messages, source="uia", may_be_incomplete=True
    )

    conversation = database.connection.execute(
        "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
    ).fetchone()
    rows = database.connection.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY sequence_number",
        (conversation_id,),
    ).fetchall()
    assert conversation["customer_id"] == customer_id
    assert conversation["title"] == "Alice WhatsApp"
    assert conversation["source"] == "uia"
    assert conversation["started_at"] == "2026-11-21 10:30"
    assert conversation["last_message_at"] == "2026-11-21 10:31"
    assert len(rows) == 2
    assert rows[0]["sender_type"] == "customer"
    assert rows[0]["content"] == "Need quotation for 500 units"
    assert rows[0]["source"] == "uia"
    assert rows[0]["recognized_at"] == "2026-11-21T08:00:00Z"
    assert rows[0]["recognition_confidence"] == pytest.approx(0.95)
    assert rows[0]["may_be_incomplete"] == 1
    assert [row["sequence_number"] for row in rows] == [1, 2]
    assert database.connection.execute(
        "SELECT rowid FROM message_search WHERE message_search MATCH 'quotation'"
    ).fetchone()[0] == rows[0]["id"]


def test_save_capture_uses_recognition_time_when_message_time_is_unknown(database):
    customer_id = _customer(database)
    service = ConversationService(database)

    conversation_id = service.save_capture(
        customer_id,
        "Manual capture",
        [CapturedMessage("Visible only", recognized_at="2026-11-21T08:00:00Z")],
    )

    conversation = database.connection.execute(
        "SELECT started_at, last_message_at FROM conversations WHERE id = ?",
        (conversation_id,),
    ).fetchone()
    assert conversation["started_at"] == "2026-11-21T08:00:00Z"
    assert conversation["last_message_at"] == "2026-11-21T08:00:00Z"


def test_save_capture_validates_customer_and_messages_before_writing(database):
    customer_id = _customer(database)
    service = ConversationService(database)

    with pytest.raises(ConversationValidationError, match="至少一条"):
        service.save_capture(customer_id, "Empty", [])
    with pytest.raises(ConversationValidationError, match="客户"):
        service.save_capture(999999, "Missing", [CapturedMessage("Hello")])

    assert database.connection.execute(
        "SELECT COUNT(*) FROM conversations"
    ).fetchone()[0] == 0
    assert database.connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
