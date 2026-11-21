"""客户历史会话与消息检索，严格限定在单个客户范围。"""

from __future__ import annotations

from app.database.connection import Database
from app.models.history import HistoryConversation, HistoryMessage


class HistoryRepository:
    def __init__(self, database: Database):
        self.database = database

    def list_conversations(
        self, customer_id: int, search: str = ""
    ) -> list[HistoryConversation]:
        keyword = str(search or "").strip()
        pattern = f"%{keyword}%"
        rows = self.database.connection.execute(
            """
            SELECT c.id, c.customer_id, c.title, c.source, c.started_at,
                   c.last_message_at, COUNT(m.id) AS message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.customer_id = ?
              AND (
                ? = ''
                OR c.title LIKE ?
                OR EXISTS (
                    SELECT 1 FROM messages matched
                    WHERE matched.conversation_id = c.id AND matched.content LIKE ?
                )
              )
            GROUP BY c.id
            ORDER BY COALESCE(c.last_message_at, c.created_at) DESC, c.id DESC
            """,
            (customer_id, keyword, pattern, pattern),
        ).fetchall()
        return [HistoryConversation.from_row(row) for row in rows]

    def list_messages(
        self, customer_id: int, conversation_id: int, search: str = ""
    ) -> list[HistoryMessage]:
        keyword = str(search or "").strip()
        pattern = f"%{keyword}%"
        rows = self.database.connection.execute(
            """
            SELECT m.id, m.conversation_id, m.sender_type, m.content,
                   m.message_timestamp, m.sequence_number, m.source
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE c.customer_id = ? AND c.id = ?
              AND (? = '' OR m.content LIKE ?)
            ORDER BY m.sequence_number, m.id
            """,
            (customer_id, conversation_id, keyword, pattern),
        ).fetchall()
        return [HistoryMessage.from_row(row) for row in rows]
