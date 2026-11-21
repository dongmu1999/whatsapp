"""客户历史记录：记忆摘要、待确认建议、记忆维护与历史聊天检索。"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.memory import (
    CATEGORY_LABELS,
    MEMORY_CATEGORIES,
    MemoryValidationError,
    SOURCE_LABELS,
    STATUS_LABELS,
)

logger = logging.getLogger(__name__)

_SENDER_LABELS = {"customer": "客户", "sales": "销售", "unknown": "未知"}


def _empty_summary_label() -> QLabel:
    label = QLabel("尚未选择客户")
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return label


class CustomerHistoryPage(QWidget):
    status_message = Signal(str)
    memories_changed = Signal()

    def __init__(self, customer_service, memory_service, parent=None):
        super().__init__(parent)
        self.customer_service = customer_service
        self.memory_service = memory_service
        self._history_search = ""
        self.setObjectName("customerHistoryPage")
        self._build_ui()
        self.refresh_customers()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)
        scroll.setWidget(content)

        title = QLabel("客户历史记录")
        title.setObjectName("pageHeading")
        layout.addWidget(title)
        subtitle = QLabel(
            "查看单个客户的历史聊天与长期记忆。AI 只生成待确认建议，确认前不会写入正式记忆。"
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        selector = QFrame()
        selector.setObjectName("card")
        selector_layout = QHBoxLayout(selector)
        selector_layout.setContentsMargins(16, 12, 16, 12)
        selector_layout.addWidget(QLabel("当前客户"))
        self.customer_combo = QComboBox()
        self.customer_combo.setObjectName("historyCustomerCombo")
        self.customer_combo.setMinimumWidth(240)
        self.customer_combo.currentIndexChanged.connect(self.load_customer)
        selector_layout.addWidget(self.customer_combo)
        selector_layout.addStretch(1)
        self.status_label = QLabel("请选择客户以查看记忆与历史。")
        self.status_label.setObjectName("mutedText")
        self.status_label.setWordWrap(True)
        selector_layout.addWidget(self.status_label)
        layout.addWidget(selector)

        summary_card = QFrame()
        summary_card.setObjectName("card")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(18, 16, 18, 16)
        summary_title = QLabel("客户记忆摘要（仅已确认）")
        summary_title.setObjectName("sectionHeading")
        summary_layout.addWidget(summary_title)
        self.memory_summary_label = _empty_summary_label()
        summary_layout.addWidget(self.memory_summary_label)
        layout.addWidget(summary_card)

        suggestions_card = QFrame()
        suggestions_card.setObjectName("card")
        suggestions_layout = QVBoxLayout(suggestions_card)
        suggestions_layout.setContentsMargins(18, 16, 18, 16)
        suggestions_title = QLabel("AI 记忆建议（待人工确认）")
        suggestions_title.setObjectName("sectionHeading")
        suggestions_layout.addWidget(suggestions_title)
        hint = QLabel("AI 建议不会自动成为正式记忆；请核对后再确认或忽略。")
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        suggestions_layout.addWidget(hint)
        self.suggestion_table = self._make_table(("分类", "建议内容", "依据"))
        suggestions_layout.addWidget(self.suggestion_table)
        suggestion_actions = QHBoxLayout()
        self.confirm_suggestion_button = QPushButton("确认所选建议")
        self.confirm_suggestion_button.setObjectName("primaryButton")
        self.confirm_suggestion_button.clicked.connect(self.confirm_selected_suggestion)
        suggestion_actions.addWidget(self.confirm_suggestion_button)
        self.reject_suggestion_button = QPushButton("忽略所选建议")
        self.reject_suggestion_button.clicked.connect(self.reject_selected_suggestion)
        suggestion_actions.addWidget(self.reject_suggestion_button)
        suggestion_actions.addStretch(1)
        suggestions_layout.addLayout(suggestion_actions)
        layout.addWidget(suggestions_card)

        memory_card = QFrame()
        memory_card.setObjectName("card")
        memory_layout = QVBoxLayout(memory_card)
        memory_layout.setContentsMargins(18, 16, 18, 16)
        memory_title = QLabel("客户记忆维护")
        memory_title.setObjectName("sectionHeading")
        memory_layout.addWidget(memory_title)
        add_row = QHBoxLayout()
        self.memory_category_combo = QComboBox()
        self.memory_category_combo.setObjectName("memoryCategoryCombo")
        for key, label in MEMORY_CATEGORIES:
            self.memory_category_combo.addItem(label, key)
        add_row.addWidget(self.memory_category_combo)
        self.memory_content_edit = QLineEdit()
        self.memory_content_edit.setObjectName("memoryContentEdit")
        self.memory_content_edit.setPlaceholderText("手动添加一条已核实的客户记忆")
        self.memory_content_edit.returnPressed.connect(self.add_memory)
        add_row.addWidget(self.memory_content_edit, 1)
        self.add_memory_button = QPushButton("添加记忆")
        self.add_memory_button.clicked.connect(self.add_memory)
        add_row.addWidget(self.add_memory_button)
        memory_layout.addLayout(add_row)
        self.memory_table = self._make_table(("分类", "内容", "来源", "状态"))
        memory_layout.addWidget(self.memory_table)
        memory_actions = QHBoxLayout()
        self.save_memory_button = QPushButton("保存所选内容修改")
        self.save_memory_button.clicked.connect(self.save_selected_memory)
        memory_actions.addWidget(self.save_memory_button)
        self.delete_memory_button = QPushButton("删除所选记忆")
        self.delete_memory_button.clicked.connect(self.delete_selected_memory)
        memory_actions.addWidget(self.delete_memory_button)
        memory_actions.addStretch(1)
        memory_layout.addLayout(memory_actions)
        layout.addWidget(memory_card)

        history_card = QFrame()
        history_card.setObjectName("card")
        history_layout = QVBoxLayout(history_card)
        history_layout.setContentsMargins(18, 16, 18, 16)
        history_title = QLabel("客户历史聊天")
        history_title.setObjectName("sectionHeading")
        history_layout.addWidget(history_title)
        search_row = QHBoxLayout()
        self.history_search_edit = QLineEdit()
        self.history_search_edit.setObjectName("historySearchEdit")
        self.history_search_edit.setPlaceholderText("按标题或消息内容搜索该客户的历史聊天")
        self.history_search_edit.returnPressed.connect(self.search_history)
        search_row.addWidget(self.history_search_edit, 1)
        self.search_button = QPushButton("搜索")
        self.search_button.clicked.connect(self.search_history)
        search_row.addWidget(self.search_button)
        history_layout.addLayout(search_row)
        self.history_table = self._make_table(("最近消息", "会话标题", "消息数"))
        self.history_table.itemSelectionChanged.connect(self._load_conversation_messages)
        history_layout.addWidget(self.history_table)
        self.history_detail = QPlainTextEdit()
        self.history_detail.setObjectName("historyDetail")
        self.history_detail.setReadOnly(True)
        self.history_detail.setMinimumHeight(140)
        history_layout.addWidget(self.history_detail)
        layout.addWidget(history_card)
        layout.addStretch(1)

    @staticmethod
    def _make_table(headers: tuple[str, ...]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setMinimumHeight(130)
        return table

    def refresh_customers(self) -> None:
        current = self.customer_combo.currentData()
        self.customer_combo.blockSignals(True)
        self.customer_combo.clear()
        self.customer_combo.addItem("请选择客户", None)
        for customer in self.customer_service.list():
            label = customer.name
            if customer.company_name:
                label += f" · {customer.company_name}"
            self.customer_combo.addItem(label, customer.id)
        index = self.customer_combo.findData(current) if current is not None else 0
        self.customer_combo.setCurrentIndex(max(0, index))
        self.customer_combo.blockSignals(False)
        self.load_customer()

    def current_customer_id(self):
        return self.customer_combo.currentData()

    def load_customer(self) -> None:
        customer_id = self.current_customer_id()
        if customer_id is None:
            self.memory_summary_label.setText("尚未选择客户")
            self.suggestion_table.setRowCount(0)
            self.memory_table.setRowCount(0)
            self.history_table.setRowCount(0)
            self.history_detail.clear()
            self.status_label.setText("请选择客户以查看记忆与历史。")
            return
        self.refresh()

    def refresh(self) -> None:
        customer_id = self.current_customer_id()
        if customer_id is None:
            return
        try:
            summary = self.memory_service.summary(customer_id)
            pending = self.memory_service.pending(customer_id)
            memories = self.memory_service.list_memories(customer_id)
            conversations = self.memory_service.history(customer_id, self._history_search)
        except Exception as exc:  # 数据库损坏等本地错误不应使界面崩溃
            logger.exception("加载客户记忆或历史失败")
            self.status_label.setText(f"加载失败：{exc}")
            return

        self.memory_summary_label.setText(summary or "暂无已确认的客户记忆。")
        self._fill_suggestions(pending)
        self._fill_memories(memories)
        self._fill_history(conversations)
        self.status_label.setText(
            f"已加载 {len(memories)} 条记忆、{len(pending)} 条待确认建议、{len(conversations)} 个会话。"
        )

    def _find_memory(self, memory_id: int):
        customer_id = self.current_customer_id()
        if customer_id is None:
            return None
        for memory in self.memory_service.list_memories(customer_id):
            if memory.id == memory_id:
                return memory
        return None

    def _fill_suggestions(self, memories) -> None:
        self.suggestion_table.setRowCount(0)
        for row, memory in enumerate(memories):
            self.suggestion_table.insertRow(row)
            category = QTableWidgetItem(CATEGORY_LABELS.get(memory.category, memory.category))
            category.setData(Qt.UserRole, memory.id)
            self.suggestion_table.setItem(row, 0, category)
            self.suggestion_table.setItem(row, 1, QTableWidgetItem(memory.content))
            self.suggestion_table.setItem(row, 2, QTableWidgetItem("AI 分析建议"))

    def _fill_memories(self, memories) -> None:
        self.memory_table.setRowCount(0)
        for row, memory in enumerate(memories):
            self.memory_table.insertRow(row)
            category = QTableWidgetItem(CATEGORY_LABELS.get(memory.category, memory.category))
            category.setData(Qt.UserRole, memory.id)
            self.memory_table.setItem(row, 0, category)
            self.memory_table.setItem(row, 1, QTableWidgetItem(memory.content))
            self.memory_table.setItem(
                row, 2, QTableWidgetItem(SOURCE_LABELS.get(memory.source, memory.source))
            )
            self.memory_table.setItem(
                row, 3, QTableWidgetItem(STATUS_LABELS.get(memory.status, memory.status))
            )

    def _fill_history(self, conversations) -> None:
        self.history_table.setRowCount(0)
        for row, conversation in enumerate(conversations):
            self.history_table.insertRow(row)
            time_item = QTableWidgetItem(
                (conversation.last_message_at or conversation.started_at or "—")[:16].replace(
                    "T", " "
                )
            )
            time_item.setData(Qt.UserRole, conversation.id)
            self.history_table.setItem(row, 0, time_item)
            self.history_table.setItem(row, 1, QTableWidgetItem(conversation.title))
            self.history_table.setItem(row, 2, QTableWidgetItem(str(conversation.message_count)))
        self.history_detail.clear()
        if conversations:
            self.history_table.selectRow(0)
            self._load_conversation_messages()
        else:
            self.history_detail.setPlainText(
                "未找到匹配的历史会话。" if self._history_search else "该客户暂无历史会话。"
            )

    def add_memory(self) -> bool:
        customer_id = self.current_customer_id()
        if customer_id is None:
            self.status_label.setText("请先选择客户。")
            return False
        try:
            self.memory_service.add_manual(
                customer_id,
                self.memory_category_combo.currentData(),
                self.memory_content_edit.text(),
            )
        except MemoryValidationError as exc:
            self.status_label.setText(str(exc))
            return False
        self.memory_content_edit.clear()
        self.refresh()
        self.status_label.setText("已添加并确认一条客户记忆。")
        self.memories_changed.emit()
        return True

    def save_selected_memory(self) -> bool:
        customer_id = self.current_customer_id()
        row = self.memory_table.currentRow()
        if customer_id is None or row < 0:
            self.status_label.setText("请选择要修改的记忆。")
            return False
        memory_id = self.memory_table.item(row, 0).data(Qt.UserRole)
        content = self.memory_table.item(row, 1).text() if self.memory_table.item(row, 1) else ""
        current = self._find_memory(memory_id)
        if current is None:
            self.status_label.setText("所选记忆不存在或不属于当前客户。")
            return False
        try:
            self.memory_service.update_memory(
                customer_id, memory_id, category=current.category, content=content
            )
        except MemoryValidationError as exc:
            self.status_label.setText(str(exc))
            return False
        self.refresh()
        self.status_label.setText("已保存所选记忆的修改。")
        self.memories_changed.emit()
        return True

    def _selected_suggestion_id(self):
        row = self.suggestion_table.currentRow()
        if row < 0 or self.suggestion_table.item(row, 0) is None:
            return None
        return self.suggestion_table.item(row, 0).data(Qt.UserRole)

    def confirm_selected_suggestion(self) -> bool:
        customer_id = self.current_customer_id()
        memory_id = self._selected_suggestion_id()
        if customer_id is None or memory_id is None:
            self.status_label.setText("请选择要确认的 AI 记忆建议。")
            return False
        self.memory_service.confirm(customer_id, memory_id)
        self.refresh()
        self.status_label.setText("已确认所选建议，并写入正式客户记忆。")
        self.memories_changed.emit()
        return True

    def reject_selected_suggestion(self) -> bool:
        customer_id = self.current_customer_id()
        memory_id = self._selected_suggestion_id()
        if customer_id is None or memory_id is None:
            self.status_label.setText("请选择要忽略的 AI 记忆建议。")
            return False
        self.memory_service.reject(customer_id, memory_id)
        self.refresh()
        self.status_label.setText("已忽略所选 AI 建议，未写入正式记忆。")
        self.memories_changed.emit()
        return True

    def delete_selected_memory(self) -> bool:
        customer_id = self.current_customer_id()
        row = self.memory_table.currentRow()
        if customer_id is None or row < 0 or self.memory_table.item(row, 0) is None:
            self.status_label.setText("请选择要删除的客户记忆。")
            return False
        memory_id = self.memory_table.item(row, 0).data(Qt.UserRole)
        if not self.memory_service.delete_memory(customer_id, memory_id):
            self.status_label.setText("所选记忆不存在或不属于当前客户。")
            return False
        self.refresh()
        self.status_label.setText("已删除所选客户记忆。")
        self.memories_changed.emit()
        return True

    def search_history(self) -> bool:
        customer_id = self.current_customer_id()
        if customer_id is None:
            self.status_label.setText("请先选择客户。")
            return False
        self._history_search = self.history_search_edit.text().strip()
        conversations = self.memory_service.history(customer_id, self._history_search)
        self._fill_history(conversations)
        self.status_label.setText(
            f"历史搜索：找到 {len(conversations)} 个相关会话。"
            if self._history_search
            else f"已显示 {len(conversations)} 个历史会话。"
        )
        return bool(conversations)

    def _load_conversation_messages(self) -> None:
        customer_id = self.current_customer_id()
        row = self.history_table.currentRow()
        if customer_id is None or row < 0 or self.history_table.item(row, 0) is None:
            self.history_detail.clear()
            return
        conversation_id = self.history_table.item(row, 0).data(Qt.UserRole)
        messages = self.memory_service.messages(
            customer_id, conversation_id, self._history_search
        )
        if not messages:
            self.history_detail.setPlainText("没有匹配的消息内容。")
            return
        self.history_detail.setPlainText(
            "\n\n".join(
                f"[{_SENDER_LABELS.get(message.sender_type, message.sender_type)}] "
                f"{message.content}"
                for message in messages
            )
        )
