"""系统设置、备份恢复与本地数据保留。"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_VERSION
from app.ui.theme import DARK_THEME, LIGHT_THEME

logger = logging.getLogger(__name__)


class SettingsPage(QWidget):
    theme_requested = Signal(str)
    data_restored = Signal()
    status_message = Signal(str)

    def __init__(
        self,
        current_theme: str,
        data_dir: Path,
        parent=None,
        *,
        backup_service=None,
        maintenance_service=None,
        settings_repository=None,
    ):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self.data_dir = Path(data_dir)
        self.backup_service = backup_service
        self.maintenance_service = maintenance_service
        self.settings_repository = settings_repository

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)

        heading = QLabel("系统设置")
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)
        subtitle = QLabel("管理本地界面偏好、数据备份与隐私保留策略。")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)

        content_layout.addWidget(self._build_preference_card())
        content_layout.addWidget(self._build_backup_card())
        content_layout.addWidget(self._build_privacy_card())
        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        self.set_theme(current_theme)
        self.refresh_state()

    def _build_preference_card(self) -> QFrame:
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

        data_path = QLineEdit(str(self.data_dir))
        data_path.setReadOnly(True)
        data_path.setObjectName("dataPath")
        form.addRow("本地数据目录", data_path)

        self.version_label = QLabel(f"SalesPilot AI V{APP_VERSION} · 阶段 9")
        self.version_label.setObjectName("mutedText")
        form.addRow("当前版本", self.version_label)
        return card

    def _build_backup_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("备份与恢复")
        title.setObjectName("sectionHeading")
        layout.addWidget(title)

        note = QLabel(
            "备份包包含本地数据库和知识库文件副本，不包含系统凭据库中的 API Key。"
            "恢复前会自动创建一份安全备份，校验通过后才替换当前数据；恢复失败会回滚。"
        )
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        layout.addWidget(note)

        directory_row = QHBoxLayout()
        directory_row.setSpacing(8)
        self.backup_dir_edit = QLineEdit()
        self.backup_dir_edit.setReadOnly(True)
        self.backup_dir_edit.setObjectName("backupDirPath")
        self.choose_backup_dir_button = QPushButton("选择目录")
        self.choose_backup_dir_button.clicked.connect(self.choose_backup_dir)
        directory_row.addWidget(self.backup_dir_edit, 1)
        directory_row.addWidget(self.choose_backup_dir_button)
        layout.addLayout(directory_row)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        self.backup_button = QPushButton("立即备份")
        self.backup_button.setObjectName("primaryButton")
        self.backup_button.clicked.connect(self.create_backup)
        self.restore_button = QPushButton("从备份恢复")
        self.restore_button.clicked.connect(lambda: self.restore_backup())
        button_row.addWidget(self.backup_button)
        button_row.addWidget(self.restore_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.backup_status_label = QLabel("尚未执行备份。")
        self.backup_status_label.setObjectName("mutedText")
        self.backup_status_label.setWordWrap(True)
        layout.addWidget(self.backup_status_label)

        enabled = self.backup_service is not None
        for widget in (
            self.backup_button,
            self.restore_button,
            self.choose_backup_dir_button,
        ):
            widget.setEnabled(enabled)
        if not enabled:
            self.backup_status_label.setText("备份服务不可用，当前无法备份或恢复。")
        return card

    def _build_privacy_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("隐私与数据保留")
        title.setObjectName("sectionHeading")
        layout.addWidget(title)

        privacy_text = QLabel(
            "客户数据默认仅保存在本机 SQLite 数据库。调用 DeepSeek 分析前，"
            "软件会显示发送范围并提供脱敏选项；API Key 由系统安全凭据库保存；"
            "不会自动发送 WhatsApp 消息，也不会收集遥测数据。"
        )
        privacy_text.setObjectName("mutedText")
        privacy_text.setWordWrap(True)
        layout.addWidget(privacy_text)

        retention_row = QHBoxLayout()
        retention_row.setSpacing(10)
        retention_label = QLabel("聊天保留期限")
        self.retention_spin = QSpinBox()
        self.retention_spin.setObjectName("retentionSpin")
        self.retention_spin.setRange(0, 3650)
        self.retention_spin.setValue(0)
        self.retention_spin.setSpecialValueText("永久保留")
        self.retention_spin.setSuffix(" 天")
        self.retention_spin.setToolTip(
            "超过保留期限的聊天会话会在启动时自动清理；0 表示永久保留。"
        )
        self.save_retention_button = QPushButton("保存保留期限")
        self.save_retention_button.clicked.connect(self.save_retention)
        retention_row.addWidget(retention_label)
        retention_row.addWidget(self.retention_spin)
        retention_row.addWidget(self.save_retention_button)
        retention_row.addStretch(1)
        layout.addLayout(retention_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        self.clean_expired_button = QPushButton("立即清理过期聊天")
        self.clean_expired_button.clicked.connect(lambda: self.clean_expired_chats())
        self.clean_screenshots_button = QPushButton("清理临时截图")
        self.clean_screenshots_button.clicked.connect(self.clean_screenshots)
        self.clear_data_button = QPushButton("清空全部数据")
        self.clear_data_button.setObjectName("dangerButton")
        self.clear_data_button.clicked.connect(lambda: self.clear_all_data())
        action_row.addWidget(self.clean_expired_button)
        action_row.addWidget(self.clean_screenshots_button)
        action_row.addWidget(self.clear_data_button)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self.privacy_status_label = QLabel("清理操作只影响本机数据，不会调用网络。")
        self.privacy_status_label.setObjectName("mutedText")
        self.privacy_status_label.setWordWrap(True)
        layout.addWidget(self.privacy_status_label)

        enabled = self.maintenance_service is not None
        for widget in (
            self.retention_spin,
            self.save_retention_button,
            self.clean_expired_button,
            self.clean_screenshots_button,
            self.clear_data_button,
        ):
            widget.setEnabled(enabled)
        if not enabled:
            self.privacy_status_label.setText("数据维护服务不可用。")
        return card

    def refresh_state(self) -> None:
        if self.backup_service is not None:
            self.backup_dir_edit.setText(str(self.backup_service.backup_dir))
        else:
            self.backup_dir_edit.setText(str(self.data_dir / "backups"))
        if self.maintenance_service is not None:
            self.retention_spin.blockSignals(True)
            self.retention_spin.setValue(self.maintenance_service.get_retention_days())
            self.retention_spin.blockSignals(False)

    def _emit_theme(self) -> None:
        self.theme_requested.emit(str(self.theme_combo.currentData()))

    def set_theme(self, theme: str) -> None:
        index = self.theme_combo.findData(theme)
        if index < 0:
            return
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(index)
        self.theme_combo.blockSignals(False)

    def _notify(self, message: str) -> None:
        self.status_message.emit(message)

    def _set_backup_status(self, message: str) -> None:
        self.backup_status_label.setText(message)
        self._notify(message)

    def _set_privacy_status(self, message: str) -> None:
        self.privacy_status_label.setText(message)
        self._notify(message)

    def choose_backup_dir(self) -> None:
        if self.backup_service is None:
            return
        selected = QFileDialog.getExistingDirectory(
            self, "选择备份目录", str(self.backup_service.backup_dir)
        )
        if selected:
            self.set_backup_dir(selected)

    def set_backup_dir(self, path: str | Path) -> bool:
        if self.backup_service is None:
            self._set_backup_status("备份服务不可用。")
            return False
        try:
            target = self.backup_service.set_backup_dir(path)
        except Exception as exc:
            logger.exception("设置备份目录失败")
            self._set_backup_status(f"设置备份目录失败：{exc}")
            return False
        self.backup_dir_edit.setText(str(target))
        self._set_backup_status(f"备份目录已设置为：{target}")
        return True

    def create_backup(self) -> bool:
        if self.backup_service is None:
            self._set_backup_status("备份服务不可用。")
            return False
        try:
            info = self.backup_service.create_backup()
        except Exception as exc:
            logger.exception("创建备份失败")
            self._set_backup_status(f"备份失败：{exc}")
            return False
        self.backup_dir_edit.setText(str(info.path.parent))
        self._set_backup_status(f"备份成功：{info.path}")
        return True

    def restore_backup(self, archive: str | Path | None = None, *, confirm: bool = True) -> bool:
        if self.backup_service is None:
            self._set_backup_status("备份服务不可用。")
            return False
        selected = archive
        if selected is None:
            chosen, _ = QFileDialog.getOpenFileName(
                self,
                "选择备份文件",
                str(self.backup_service.backup_dir),
                "SalesPilot 备份 (*.zip)",
            )
            if not chosen:
                return False
            selected = chosen
        if confirm:
            answer = QMessageBox.question(
                self,
                "确认恢复备份",
                "恢复会替换当前数据库和知识库文件。软件会先自动创建安全备份，"
                "但当前数据仍会被覆盖。是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return False
        try:
            result = self.backup_service.restore_backup(selected)
        except Exception as exc:
            logger.exception("恢复备份失败")
            self._set_backup_status(f"恢复失败：{exc}")
            return False
        self.refresh_state()
        self._set_backup_status(
            f"恢复完成：已从 {Path(selected).name} 恢复；"
            f"恢复前安全备份：{result.safety_backup.name}"
        )
        self.data_restored.emit()
        return True

    def save_retention(self) -> bool:
        if self.maintenance_service is None:
            self._set_privacy_status("数据维护服务不可用。")
            return False
        try:
            days = self.maintenance_service.set_retention_days(
                self.retention_spin.value()
            )
        except Exception as exc:
            logger.exception("保存聊天保留期限失败")
            self._set_privacy_status(f"保存保留期限失败：{exc}")
            return False
        self._set_privacy_status(
            "聊天保留期限已保存：永久保留"
            if days == 0
            else f"聊天保留期限已保存：{days} 天"
        )
        return True

    def clean_expired_chats(self, *, confirm: bool = True) -> bool:
        if self.maintenance_service is None:
            self._set_privacy_status("数据维护服务不可用。")
            return False
        if confirm:
            answer = QMessageBox.question(
                self,
                "确认清理聊天",
                "将删除超过保留期限的聊天会话及其消息。客户、分析和记忆不会删除。是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return False
        try:
            removed = self.maintenance_service.apply_retention()
        except Exception as exc:
            logger.exception("清理过期聊天失败")
            self._set_privacy_status(f"清理过期聊天失败：{exc}")
            return False
        if self.maintenance_service.get_retention_days() == 0:
            self._set_privacy_status("当前设置为永久保留，未清理任何聊天。")
        else:
            self._set_privacy_status(f"已清理 {removed} 个过期聊天会话。")
        return True

    def clean_screenshots(self) -> bool:
        if self.maintenance_service is None:
            self._set_privacy_status("数据维护服务不可用。")
            return False
        try:
            removed = self.maintenance_service.cleanup_temp_screenshots()
        except Exception as exc:
            logger.exception("清理临时截图失败")
            self._set_privacy_status(f"清理临时截图失败：{exc}")
            return False
        self._set_privacy_status(f"已清理 {removed} 个过期临时截图文件。")
        return True

    def clear_all_data(self, *, confirm: bool = True) -> bool:
        if self.maintenance_service is None:
            self._set_privacy_status("数据维护服务不可用。")
            return False
        if confirm:
            answer = QMessageBox.warning(
                self,
                "确认清空全部数据",
                "将永久删除所有客户、聊天、分析、记忆、知识库文档、产品资料和跟进任务，"
                "并删除知识库文件副本。系统设置会保留，此操作不可撤销。是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return False
        try:
            self.maintenance_service.clear_all_data()
        except Exception as exc:
            logger.exception("清空全部数据失败")
            self._set_privacy_status(f"清空全部数据失败：{exc}")
            return False
        self._set_privacy_status("已清空全部本地业务数据，系统设置已保留。")
        self.data_restored.emit()
        return True
