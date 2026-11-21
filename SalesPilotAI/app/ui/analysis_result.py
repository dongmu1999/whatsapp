"""结构化销售分析与三种可复制回复，不包含发送功能。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.analysis import REPLY_TYPES, SalesAnalysis


_REPLY_TITLES = {
    "professional": "专业型 · Professional",
    "sales_driven": "销售推进型 · Sales Driven",
    "relationship_building": "关系建立型 · Relationship Building",
}


def _wrapped_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return label


def _list_text(values: list[str]) -> str:
    return "\n".join(f"• {value}" for value in values) if values else "暂无明确依据"


class ReplySuggestionCard(QFrame):
    copy_requested = Signal(str)

    def __init__(self, reply_type: str, parent=None):
        super().__init__(parent)
        self.reply_type = reply_type
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        title = QLabel(_REPLY_TITLES[reply_type])
        title.setObjectName("sectionHeading")
        layout.addWidget(title)
        self.english_edit = QPlainTextEdit()
        self.english_edit.setPlaceholderText("AI 英文回复，可在复制前编辑")
        self.english_edit.setMaximumHeight(110)
        layout.addWidget(self.english_edit)
        self.chinese_label = _wrapped_label()
        self.strategy_label = _wrapped_label()
        self.use_case_label = _wrapped_label()
        layout.addWidget(self.chinese_label)
        layout.addWidget(self.strategy_label)
        layout.addWidget(self.use_case_label)
        self.copy_button = QPushButton("复制英文回复")
        self.copy_button.clicked.connect(lambda: self.copy_requested.emit(self.reply_type))
        layout.addWidget(self.copy_button, 0, Qt.AlignRight)

    def set_reply(self, reply) -> None:
        self.english_edit.setPlainText(reply.english)
        self.chinese_label.setText(f"中文翻译：{reply.chinese}")
        self.strategy_label.setText(f"策略：{reply.strategy}")
        self.use_case_label.setText(f"适用场景：{reply.use_case}")


class AnalysisResultWidget(QWidget):
    status_message = Signal(str)
    followup_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.analysis: SalesAnalysis | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        heading = QLabel("AI 销售分析结果")
        heading.setObjectName("sectionHeading")
        layout.addWidget(heading)

        summary = QFrame()
        summary.setObjectName("card")
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(18, 16, 18, 16)
        metrics = QHBoxLayout()
        self.score_label = QLabel("— / 100")
        self.score_label.setObjectName("analysisScore")
        self.confidence_label = QLabel("置信度：—")
        self.intent_label = QLabel("客户意图：等待分析")
        metrics.addWidget(self.score_label)
        metrics.addWidget(self.confidence_label)
        metrics.addWidget(self.intent_label, 1)
        summary_layout.addLayout(metrics)
        self.form = QFormLayout()
        self.form.setVerticalSpacing(10)
        self.value_labels = {}
        fields = (
            ("translation", "最新消息中文翻译"),
            ("customer_intent_explanation", "意图判断依据"),
            ("customer_emotion", "客户情绪"),
            ("sales_stage", "销售阶段"),
            ("purchase_requirements", "采购需求"),
            ("score_evidence", "评分证据"),
            ("customer_concerns", "客户顾虑"),
            ("price_sensitivity", "价格敏感度"),
            ("communication_risks", "沟通风险"),
            ("opportunities", "销售机会"),
            ("recommended_strategy", "推荐策略"),
            ("next_questions", "下一步问题"),
            ("followup_suggestion", "跟进建议"),
            ("unknown_information", "未知信息"),
        )
        for key, title in fields:
            value = _wrapped_label("—")
            self.value_labels[key] = value
            self.form.addRow(title, value)
        self.knowledge_label = _wrapped_label("—")
        self.form.addRow("知识库引用", self.knowledge_label)
        summary_layout.addLayout(self.form)
        layout.addWidget(summary)

        self.followup_button = QPushButton("根据建议创建跟进任务…")
        self.followup_button.setToolTip(
            "只把 AI 建议填入跟进表单，仍需你核对客户、时间和内容后手动创建；不会发送 WhatsApp 消息。"
        )
        self.followup_button.clicked.connect(self.followup_requested)
        self.followup_button.setVisible(False)
        layout.addWidget(self.followup_button, 0, Qt.AlignLeft)

        replies_heading = QLabel("三种回复策略（仅复制，不会自动发送）")
        replies_heading.setObjectName("sectionHeading")
        layout.addWidget(replies_heading)
        self.reply_cards = {}
        for reply_type in REPLY_TYPES:
            card = ReplySuggestionCard(reply_type)
            card.copy_requested.connect(self.copy_reply)
            self.reply_cards[reply_type] = card
            layout.addWidget(card)

    def set_analysis(self, analysis: SalesAnalysis) -> None:
        self.analysis = analysis
        self.followup_button.setVisible(analysis.followup_required)
        if analysis.followup_required:
            if analysis.followup_due_days is None:
                self.followup_button.setText("根据建议创建跟进任务…")
            else:
                self.followup_button.setText(
                    f"建议 {analysis.followup_due_days} 天后跟进，手动创建任务…"
                )
        self.score_label.setText(f"{analysis.purchase_intent_score} / 100")
        self.confidence_label.setText(f"置信度：{analysis.confidence:.0%}")
        self.intent_label.setText(f"客户意图：{analysis.customer_intent}")
        for key, label in self.value_labels.items():
            value = getattr(analysis, key)
            if isinstance(value, list):
                text = _list_text(value)
            elif key == "followup_suggestion":
                text = ("需要跟进：" if analysis.followup_required else "暂不要求跟进：") + (
                    value or "无补充建议"
                )
            else:
                text = str(value)
            label.setText(text)
        for reply in analysis.replies:
            self.reply_cards[reply.type].set_reply(reply)
        if analysis.knowledge_references:
            self.knowledge_label.setText(
                "\n".join(
                    f"• {reference.source}：{reference.fact}"
                    for reference in analysis.knowledge_references
                )
            )
        else:
            self.knowledge_label.setText(
                "本次未引用知识库；客户说法与 AI 推测不得视为已确认资料。"
            )

    def copy_reply(self, reply_type: str) -> None:
        card = self.reply_cards[reply_type]
        QApplication.clipboard().setText(card.english_edit.toPlainText())
        self.status_message.emit(f"已复制{_REPLY_TITLES[reply_type].split(' · ')[0]}英文回复；请自行到 WhatsApp 核对并发送。")
