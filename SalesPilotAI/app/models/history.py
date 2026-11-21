"""客户历史会话与消息检索，严格限定在单个客户范围。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HistoryConversation:
    id: int
    customer_id: int
    title: str
    source: str
    started_at: str | None
    last_message_at: str | None
    message_count: int

    @classmethod
    def from_row(cls, row) -> "HistoryConversation":
        return cls(
            id=int(row["id"]),
            customer_id=int(row["customer_id"]),
            title=str(row["title"] or "未命名会话"),
            source=str(row["source"]),
            started_at=row["started_at"],
            last_message_at=row["last_message_at"],
            message_count=int(row["message_count"]),
        )


@dataclass(frozen=True, slots=True)
class HistoryMessage:
    id: int
    conversation_id: int
    sender_type: str
    content: str
    message_timestamp: str | None
    sequence_number: int
    source: str

    @classmethod
    def from_row(cls, row) -> "HistoryMessage":
        return cls(
            id=int(row["id"]),
            conversation_id=int(row["conversation_id"]),
            sender_type=str(row["sender_type"]),
            content=str(row["content"]),
            message_timestamp=row["message_timestamp"],
            sequence_number=int(row["sequence_number"]),
            source=str(row["source"]),
        )
