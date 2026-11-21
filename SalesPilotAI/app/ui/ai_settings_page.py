"""DeepSeek 配置、安全凭据与连接测试。"""

from __future__ import annotations

import logging
import sqlite3

from PySide6.QtCore import QThreadPool, Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.services.ai_settings_service import CredentialStoreError, DeepSeekConfig
from app.ui.workers import FunctionWorker

logger = logging.getLogger(__name__)


class AISettingsPage(QWidget):
    connection_finished = Signal()
    settings_saved = Signal()

    def __init__(self, service, client, usage_repository, parent=None):
        super().__init__(parent)
        self.service = service
        self.client = client
        self.usage_repository = usage_repository
        self._active_worker = None
        self.setObjectName("aiSettingsPage")
        self._build_ui()
        self.load_settings()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)
        heading = QLabel("AI 模型设置")
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)
        subtitle = QLabel("配置 DeepSeek 兼容接口。API Key 仅写入系统安全凭据库，不写入 SQLite。")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("card")
        form = QFormLayout(card)
        form.setContentsMargins(22, 20, 22, 20)
        form.setHorizontalSpacing(22)
        form.setVerticalSpacing(14)
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setObjectName("deepseekBaseUrl")
        form.addRow("Base URL", self.base_url_edit)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setObjectName("deepseekApiKey")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("留空表示保留已保存的 Key；不会回显明文")
        form.addRow("API Key", self.api_key_edit)
        self.model_edit = QLineEdit()
        self.model_edit.setObjectName("deepseekModel")
        form.addRow("默认模型", self.model_edit)
        self.advanced_model_edit = QLineEdit()
        self.advanced_model_edit.setObjectName("deepseekAdvancedModel")
        form.addRow("高级模型", self.advanced_model_edit)
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setDecimals(1)
        form.addRow("Temperature", self.temperature_spin)
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(1, 32000)
        self.max_tokens_spin.setSingleStep(100)
        form.addRow("最大输出 Token", self.max_tokens_spin)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 600)
        self.timeout_spin.setSuffix(" 秒")
        form.addRow("请求超时", self.timeout_spin)
        layout.addWidget(card)

        actions = QHBoxLayout()
        self.save_button = QPushButton("安全保存设置")
        self.save_button.setObjectName("primaryButton")
        self.save_button.clicked.connect(self.save_settings)
        actions.addWidget(self.save_button)
        self.clear_key_button = QPushButton("删除已保存 Key")
        self.clear_key_button.clicked.connect(self.clear_api_key)
        actions.addWidget(self.clear_key_button)
        self.test_button = QPushButton("测试连接")
        self.test_button.clicked.connect(self.test_connection)
        actions.addWidget(self.test_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        self.status_label = QLabel("请先保存 API Key，再测试连接。模型名称可按账户实际可用情况修改。")
        self.status_label.setObjectName("mutedText")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.usage_label = QLabel("最近连接测试：尚未执行")
        self.usage_label.setObjectName("mutedText")
        layout.addWidget(self.usage_label)
        notice = QLabel(
            "连接测试会向所配置的 DeepSeek 地址发送一条极短测试消息。分析聊天前仍会单独请求你的确认。"
        )
        notice.setObjectName("mutedText")
        notice.setWordWrap(True)
        layout.addWidget(notice)
        layout.addStretch(1)

    def load_settings(self) -> None:
        config = self.service.load()
        self.base_url_edit.setText(config.base_url)
        self.model_edit.setText(config.model)
        self.advanced_model_edit.setText(config.advanced_model)
        self.temperature_spin.setValue(config.temperature)
        self.max_tokens_spin.setValue(config.max_tokens)
        self.timeout_spin.setValue(config.timeout)

    def save_settings(self) -> bool:
        config = DeepSeekConfig(
            base_url=self.base_url_edit.text(),
            api_key=self.api_key_edit.text(),
            model=self.model_edit.text(),
            advanced_model=self.advanced_model_edit.text(),
            temperature=self.temperature_spin.value(),
            max_tokens=self.max_tokens_spin.value(),
            timeout=self.timeout_spin.value(),
        )
        try:
            self.service.save(config)
        except (ValueError, CredentialStoreError, sqlite3.Error) as exc:
            self.status_label.setText(f"设置保存失败：{exc}")
            return False
        self.api_key_edit.clear()
        self.status_label.setText("设置已保存；API Key 仅保存在系统安全凭据库中。")
        self.settings_saved.emit()
        return True

    def clear_api_key(self) -> bool:
        try:
            self.service.clear_api_key()
        except CredentialStoreError as exc:
            self.status_label.setText(str(exc))
            return False
        self.api_key_edit.clear()
        self.status_label.setText("已删除系统安全凭据库中的 DeepSeek API Key。")
        return True

    def test_connection(self) -> None:
        if self._active_worker is not None:
            return
        try:
            config = self.service.load(include_api_key=True)
        except Exception as exc:
            logger.exception("读取 DeepSeek 连接配置失败")
            self.status_label.setText(f"读取 DeepSeek 配置失败：{exc}")
            return
        self.test_button.setEnabled(False)
        self.status_label.setText("正在测试 DeepSeek 连接…")
        worker = FunctionWorker(lambda: self.client.test_connection(config))
        self._active_worker = worker
        worker.signals.result.connect(self._connection_succeeded)
        worker.signals.error.connect(self._connection_failed)
        worker.signals.finished.connect(self._connection_done)
        QThreadPool.globalInstance().start(worker)

    def _connection_succeeded(self, result) -> None:
        self.usage_repository.record(result.stats)
        self.status_label.setText(result.message)
        self.usage_label.setText(self._usage_text(result.stats))

    def _connection_failed(self, error: Exception) -> None:
        logger.error("DeepSeek 连接测试失败", exc_info=error)
        stats = getattr(error, "stats", None)
        if stats is not None:
            self.usage_repository.record(stats)
            self.usage_label.setText(self._usage_text(stats))
        if isinstance(error, (CredentialStoreError, sqlite3.Error)):
            detail = f"读取 DeepSeek 配置失败：{error}"
        elif error.__class__.__name__ == "DeepSeekAPIError":
            detail = str(error)
        else:
            detail = "连接测试失败，请检查配置和网络。"
        self.status_label.setText(detail)

    def _connection_done(self) -> None:
        self._active_worker = None
        self.test_button.setEnabled(True)
        self.connection_finished.emit()

    @staticmethod
    def _usage_text(stats) -> str:
        return (
            f"最近请求：{stats.model} · 输入 {stats.prompt_tokens} / 输出 {stats.completion_tokens} "
            f"/ 合计 {stats.total_tokens} Token · {stats.duration_ms} ms"
        )
