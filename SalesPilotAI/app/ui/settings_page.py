"""系统设置与本地数据说明。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_VERSION
from app.ui.theme import DARK_THEME, LIGHT_THEME


class SettingsPage(QWidget):
    theme_requested = Signal(str)

    def __init__(self, current_theme: str, data_dir: Path, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)

        heading = QLabel("系统设置")
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)
        subtitle = QLabel("管理本地界面偏好与查看数据存储位置。")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("card")
        form = QFormLayout(card)
        form.setContentsMargins(24, 22, 24, 22)
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(18)

        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("themeCombo")
        self.theme_combo.addItem("浅色主题", LIGHT_THEME)
        self.theme_combo.addItem("深色主题", DARK_THEME)
        self.theme_combo.currentIndexChanged.connect(self._emit_theme)
        form.addRow("界面主题", self.theme_combo)

        data_path = QLineEdit(str(data_dir))
        data_path.setReadOnly(True)
        data_path.setObjectName("dataPath")
        form.addRow("本地数据目录", data_path)

        version = QLabel(f"SalesPilot AI V{APP_VERSION} · 阶段 4")
        form.addRow("当前版本", version)
        layout.addWidget(card)

        privacy_card = QFrame()
        privacy_card.setObjectName("card")
        privacy_layout = QVBoxLayout(privacy_card)
        privacy_layout.setContentsMargins(24, 20, 24, 20)
        privacy_title = QLabel("隐私与数据")
        privacy_title.setObjectName("sectionHeading")
        privacy_layout.addWidget(privacy_title)
        privacy_text = QLabel(
            "客户数据默认仅保存在本机 SQLite 数据库。调用 DeepSeek 分析前，"
            "软件会显示发送范围并提供脱敏选项；API Key 由系统安全凭据库保存；不会自动发送 WhatsApp 消息，也不会收集遥测数据。"
        )
        privacy_text.setObjectName("mutedText")
        privacy_text.setWordWrap(True)
        privacy_layout.addWidget(privacy_text)
        layout.addWidget(privacy_card)
        layout.addStretch(1)
        self.set_theme(current_theme)

    def _emit_theme(self) -> None:
        self.theme_requested.emit(str(self.theme_combo.currentData()))

    def set_theme(self, theme: str) -> None:
        index = self.theme_combo.findData(theme)
        if index < 0:
            return
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(index)
        self.theme_combo.blockSignals(False)
