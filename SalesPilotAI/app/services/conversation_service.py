"""预览确认后的会话与消息本地事务保存。"""

from __future__ import annotations

from collections.abc import Iterable

from app.database.connection import Database
from app.models.message import CAPTURE_SOURCES, CapturedMessage, utc_now_text


class ConversationValidationError(ValueError):
    """捕获结果不满足本地保存条件。"""


class ConversationService:
    def __init__(self, database: Database):
        self.database = database

    def save_capture(
        self,
        customer_id: int,
        title: str,
        messages: Iterable[CapturedMessage],
        *,
        source: str | None = None,
        may_be_incomplete: bool = True,
    ) -> int:
        rows = list(messages)
        if not rows:
            raise ConversationValidationError("至少一条消息才能保存")
        exists = self.database.connection.execute(
            "SELECT 1 FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        if exists is None:
            raise ConversationValidationError("请选择有效客户后再保存")
        conversation_source = source or rows[0].source
        if conversation_source not in CAPTURE_SOURCES:
            raise ConversationValidationError("不支持的会话来源")

        recognized_times = [message.recognized_at or utc_now_text() for message in rows]
        timeline = [
            message.timestamp or recognized_at
            for message, recognized_at in zip(rows, recognized_times)
        ]
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO conversations(
                    customer_id, title, source, started_at, last_message_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    customer_id,
                    title.strip() or "WhatsApp 可见聊天",
                    conversation_source,
                    min(timeline),
                    max(timeline),
                ),
            )
            conversation_id = int(cursor.lastrowid)
            for sequence, (message, recognized_at) in enumerate(
                zip(rows, recognized_times), start=1
            ):
                connection.execute(
                    """
                    INSERT INTO messages(
                        conversation_id, sender_type, content, message_timestamp,
                        sequence_number, source, recognized_at, recognition_confidence,
                        may_be_incomplete
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        conversation_id,
                        message.sender_type,
                        message.content,
                        message.timestamp,
                        sequence,
                        message.source,
                        recognized_at,
                        message.confidence,
                        int(may_be_incomplete),
                    ),
                )
        return conversation_id
