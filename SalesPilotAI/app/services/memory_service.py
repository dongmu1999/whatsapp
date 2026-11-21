"""客户记忆业务规则：人工维护、AI 建议待确认、摘要与历史检索。"""

from __future__ import annotations

from collections import defaultdict

from app.models.history import HistoryConversation, HistoryMessage
from app.models.memory import (
    CATEGORY_LABELS,
    MEMORY_CATEGORIES,
    CustomerMemory,
    MemorySuggestion,
    MemoryValidationError,
    normalize_category,
    normalize_content,
    validate_content,
)
from app.models.message import utc_now_text


class MemoryService:
    def __init__(self, repository, history_repository):
        self.repository = repository
        self.history_repository = history_repository

    def _ensure_customer(self, customer_id: int) -> None:
        row = self.repository.database.connection.execute(
            "SELECT 1 FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        if row is None:
            raise MemoryValidationError("请选择有效客户后再维护客户记忆")

    def add_manual(
        self, customer_id: int, category: str, content: str
    ) -> CustomerMemory:
        self._ensure_customer(customer_id)
        category = normalize_category(category)
        content = validate_content(content)
        memory_id = self.repository.insert(
            customer_id,
            category,
            content,
            source="manual",
            status="confirmed",
            confirmed_at=utc_now_text(),
        )
        return self.repository.get(customer_id, memory_id)

    def update_memory(
        self,
        customer_id: int,
        memory_id: int,
        *,
        category: str | None = None,
        content: str | None = None,
    ) -> CustomerMemory:
        current = self.repository.get(customer_id, memory_id)
        return self.repository.update(
            customer_id,
            memory_id,
            category=normalize_category(category or current.category),
            content=validate_content(content if content is not None else current.content),
        )

    def delete_memory(self, customer_id: int, memory_id: int) -> bool:
        return self.repository.delete(customer_id, memory_id)

    def confirm(self, customer_id: int, memory_id: int) -> CustomerMemory:
        return self.repository.set_status(customer_id, memory_id, "confirmed")

    def reject(self, customer_id: int, memory_id: int) -> CustomerMemory:
        return self.repository.set_status(customer_id, memory_id, "rejected")

    def list_memories(
        self, customer_id: int, *, status: str | None = None, search: str = ""
    ) -> list[CustomerMemory]:
        return self.repository.list(customer_id, status=status, search=search)

    def pending(self, customer_id: int) -> list[CustomerMemory]:
        return self.repository.list(customer_id, status="pending")

    def summary(self, customer_id: int) -> str:
        grouped: dict[str, list[str]] = defaultdict(list)
        for memory in self.repository.list(customer_id, status="confirmed"):
            grouped[memory.category].append(memory.content)
        if not grouped:
            return ""
        sections = []
        for category, label in MEMORY_CATEGORIES:
            contents = grouped.get(category)
            if not contents:
                continue
            lines = "\n".join(f"• {content}" for content in contents)
            sections.append(f"【{label}】\n{lines}")
        return "\n\n".join(sections)

    def record_suggestions(
        self, customer_id: int, suggestions: list[MemorySuggestion]
    ) -> list[CustomerMemory]:
        self._ensure_customer(customer_id)
        existing = {
            normalize_content(memory.content)
            for memory in self.repository.list(customer_id)
            if memory.status in {"pending", "confirmed"}
        }
        created = []
        for item in suggestions:
            suggestion = MemorySuggestion.model_validate(item)
            normalized = normalize_content(suggestion.content)
            if normalized in existing:
                continue
            memory_id = self.repository.insert(
                customer_id,
                suggestion.category,
                validate_content(suggestion.content),
                source="ai_suggested",
                status="pending",
            )
            existing.add(normalized)
            created.append(self.repository.get(customer_id, memory_id))
        return created

    def history(
        self, customer_id: int, search: str = ""
    ) -> list[HistoryConversation]:
        return self.history_repository.list_conversations(customer_id, search)

    def messages(
        self, customer_id: int, conversation_id: int, search: str = ""
    ) -> list[HistoryMessage]:
        return self.history_repository.list_messages(
            customer_id, conversation_id, search
        )
