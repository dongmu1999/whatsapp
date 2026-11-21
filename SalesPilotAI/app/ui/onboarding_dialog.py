"""首次启动引导。"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class FirstRunGuideDialog(QDialog):
    """非模态首次启动说明，不阻塞主窗口。"""

    start_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("firstRunGuide")
        self.setWindowTitle("欢迎使用 SalesPilot AI")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        heading = QLabel("欢迎使用 SalesPilot AI")
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)
        subtitle = QLabel("首次使用只需完成以下步骤，所有客户数据默认保存在本机。")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        self.steps_label = QLabel(
            "1. 在“AI 模型设置”中填写 DeepSeek API Key，并点击“安全保存设置”。\n"
            "2. 打开 WhatsApp Desktop / Business，进入客户聊天后按 Ctrl+Shift+A。\n"
            "3. 在预览中逐条核对消息，再决定是否上传给 DeepSeek 分析。\n"
            "4. 客户、聊天和知识库均保存在本地，可在“系统设置”中备份、恢复或清理。"
        )
        self.steps_label.setObjectName("mutedText")
        self.steps_label.setWordWrap(True)
        self.steps_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        card_layout.addWidget(self.steps_label)
        layout.addWidget(card)

        notice = QLabel(
            "软件不会自动发送 WhatsApp 消息，不会后台监听，也不会收集遥测数据。"
        )
        notice.setObjectName("mutedText")
        notice.setWordWrap(True)
        layout.addWidget(notice)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.later_button = QPushButton("稍后设置")
        self.later_button.setObjectName("secondaryButton")
        self.later_button.clicked.connect(self.reject)
        buttons.addWidget(self.later_button)
        self.start_button = QPushButton("开始配置 API Key")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self._start)
        buttons.addWidget(self.start_button)
        layout.addLayout(buttons)

    def _start(self) -> None:
        self.start_requested.emit()
        self.accept()
