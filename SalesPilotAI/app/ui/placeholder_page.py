"""阶段 1 中明确标注的后续功能页面。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    def __init__(self, title: str, stage: str, description: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)

        heading = QLabel(title)
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)

        subtitle = QLabel(description)
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(12)

        stage_label = QLabel(stage)
        stage_label.setObjectName("sectionHeading")
        card_layout.addWidget(stage_label)

        notice = QLabel("当前版本仅完成阶段 1 基础框架，本页面将在对应开发阶段接入真实功能，不展示模拟业务数据。")
        notice.setObjectName("mutedText")
        notice.setWordWrap(True)
        card_layout.addWidget(notice)
        layout.addWidget(card)
        layout.addStretch(1)
