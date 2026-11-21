from __future__ import annotations

import pytest

from app.database.repositories.customer_repository import CustomerRepository
from app.database.repositories.history_repository import HistoryRepository
from app.database.repositories.memory_repository import MemoryRepository
from app.models.memory import (
    MemoryNotFoundError,
    MemorySuggestion,
    MemoryValidationError,
)
from app.models.message import CapturedMessage
from app.services.conversation_service import ConversationService
from app.services.customer_service import CustomerService
from app.services.memory_service import MemoryService


@pytest.fixture()
def services(database):
    customers = CustomerService(CustomerRepository(database))
    memories = MemoryService(MemoryRepository(database), HistoryRepository(database))
    conversations = ConversationService(database)
    return customers, memories, conversations


def _customer(service, name):
    return service.create({"name": name})


def _messages(*contents):
    return [
        CapturedMessage(sender_type="customer", content=content, source="manual")
        for content in contents
    ]


def test_manual_memory_is_confirmed_and_strictly_isolated_by_customer(services):
    customers, memories, _ = services
    alice = _customer(customers, "Alice")
    bob = _customer(customers, "Bob")

    memory = memories.add_manual(alice.id, "target_price", "目标价 12 美元/件")

    assert memory.status == "confirmed"
    assert memory.source == "manual"
    assert memory.confirmed_at
    assert [item.content for item in memories.list_memories(alice.id)] == ["目标价 12 美元/件"]
    assert memories.list_memories(bob.id) == []

    with pytest.raises(MemoryNotFoundError):
        memories.update_memory(bob.id, memory.id, content="被篡改")
    assert not memories.delete_memory(bob.id, memory.id)
    assert memories.list_memories(alice.id)[0].content == "目标价 12 美元/件"


def test_invalid_category_and_blank_content_are_rejected(services):
    customers, memories, _ = services
    alice = _customer(customers, "Alice")

    with pytest.raises(MemoryValidationError):
        memories.add_manual(alice.id, "unknown_category", "内容")
    with pytest.raises(MemoryValidationError):
        memories.add_manual(alice.id, "target_price", "   ")


def test_ai_suggestions_stay_pending_until_explicitly_confirmed(services):
    customers, memories, _ = services
    alice = _customer(customers, "Alice")

    created = memories.record_suggestions(
        alice.id,
        [
            MemorySuggestion(
                category="purchase_plan",
                content="计划本季度采购 500 件",
                evidence="客户说 next month 500 pcs",
            )
        ],
    )

    assert len(created) == 1
    assert created[0].status == "pending"
    assert created[0].source == "ai_suggested"
    assert created[0].confirmed_at is None
    assert memories.summary(alice.id) == ""
    assert len(memories.pending(alice.id)) == 1

    confirmed = memories.confirm(alice.id, created[0].id)

    assert confirmed.status == "confirmed"
    assert confirmed.confirmed_at
    assert memories.pending(alice.id) == []
    assert "计划本季度采购 500 件" in memories.summary(alice.id)


def test_rejected_suggestion_is_audited_but_excluded_from_summary(services):
    customers, memories, _ = services
    alice = _customer(customers, "Alice")
    suggestion = memories.record_suggestions(
        alice.id,
        [MemorySuggestion(category="price_sensitivity", content="客户对价格非常敏感")],
    )[0]

    rejected = memories.reject(alice.id, suggestion.id)

    assert rejected.status == "rejected"
    assert memories.summary(alice.id) == ""
    assert [item.status for item in memories.list_memories(alice.id)] == ["rejected"]


def test_duplicate_suggestions_are_skipped_but_can_return_after_rejection(services):
    customers, memories, _ = services
    alice = _customer(customers, "Alice")
    suggestion = MemorySuggestion(category="interested_products", content="Only LED  panel lights")
    memories.record_suggestions(alice.id, [suggestion])
    memories.record_suggestions(
        alice.id,
        [MemorySuggestion(category="interested_products", content=" only   led Panel LIGHTS ")],
    )

    assert len(memories.list_memories(alice.id)) == 1

    memories.reject(alice.id, memories.list_memories(alice.id)[0].id)
    memories.record_suggestions(alice.id, [suggestion])

    assert len(memories.pending(alice.id)) == 1


def test_summary_groups_confirmed_memories_by_category(services):
    customers, memories, _ = services
    alice = _customer(customers, "Alice")
    memories.add_manual(alice.id, "target_price", "目标价 12 美元/件")
    memories.add_manual(alice.id, "purchase_plan", "计划 12 月下单")
    memories.add_manual(alice.id, "target_price", "可接受 FOB 报价")

    summary = memories.summary(alice.id)

    assert "目标价格" in summary
    assert "采购计划" in summary
    assert summary.count("目标价 12 美元/件") == 1
    assert "可接受 FOB 报价" in summary
    assert "计划 12 月下单" in summary


def test_history_and_search_are_scoped_to_one_customer(services):
    customers, memories, conversations = services
    alice = _customer(customers, "Alice")
    bob = _customer(customers, "Bob")
    alice_conversation = conversations.save_capture(
        alice.id, "Alice 报价", _messages("Please quote MOQ 500 pcs")
    )
    conversations.save_capture(bob.id, "Bob 订单", _messages("Need MOQ 100 pcs"))

    history = memories.history(alice.id)
    assert [item.id for item in history] == [alice_conversation]
    assert history[0].message_count == 1

    matches = memories.history(alice.id, "MOQ")
    assert [item.id for item in matches] == [alice_conversation]
    assert memories.history(bob.id, "MOQ 500") == []

    messages = memories.messages(alice.id, alice_conversation, "MOQ")
    assert [message.content for message in messages] == ["Please quote MOQ 500 pcs"]
    assert memories.messages(bob.id, alice_conversation) == []


def test_edit_memory_updates_content_and_timestamp(services):
    customers, memories, _ = services
    alice = _customer(customers, "Alice")
    memory = memories.add_manual(alice.id, "core_concern", "担心交期")

    updated = memories.update_memory(
        alice.id, memory.id, category="purchase_plan", content="需要 12 月前到货"
    )

    assert updated.category == "purchase_plan"
    assert updated.content == "需要 12 月前到货"
    assert updated.updated_at >= memory.updated_at
