"""阶段 3：主动捕获、OCR/手动备用、消息预览编辑和本地保存。"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QKeySequenceEdit,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

from app.capture.errors import CaptureError
from app.capture.hotkey import parse_hotkey
from app.capture.models import CaptureResult
from app.database.repositories.settings_repository import SettingsRepository
from app.models.message import CAPTURE_SOURCES, CapturedMessage, MessageParser
from app.services.chat_capture_service import ChatCaptureService
from app.services.conversation_service import ConversationService, ConversationValidationError
from app.services.customer_service import CustomerService
from app.ui.customer_detail import CustomerEditDialog
from app.ui.region_selector import RegionSelectorDialog

logger = logging.getLogger(__name__)
_SENDER_LABELS = (("未知", "unknown"), ("客户", "customer"), ("销售", "sales"))
_SOURCE_LABELS = {"manual": "手动", "uia": "UIA", "ocr": "OCR"}
_RECOGNIZED_AT_ROLE = Qt.UserRole + 1
_CONFIDENCE_ROLE = Qt.UserRole + 2
_SENDER_NAME_ROLE = Qt.UserRole + 3


class ChatAnalysisPage(QWidget):
    hotkey_changed = Signal(str)
    customers_changed = Signal()
    status_message = Signal(str)
    result_ready = Signal()

    def __init__(
        self,
        conversation_service: ConversationService,
        customer_service: CustomerService,
        settings: SettingsRepository,
        capture_service: ChatCaptureService | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.conversation_service = conversation_service
        self.customer_service = customer_service
        self.settings = settings
        self.capture_service = capture_service or ChatCaptureService()
        self.current_source = "manual"
        self.may_be_incomplete = True
        self.setObjectName("chatAnalysisPage")
        self._build_ui()
        self._load_settings()
        self.refresh_customers()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        content = QWidget()
        content.setObjectName("pageContent")
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)

        heading = QLabel("AI 聊天分析 · 聊天捕获")
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)
        subtitle = QLabel(
            "主动获取当前可见消息，核对后再保存到本地。AI 分析将在阶段 4 提供。"
        )
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)
        notice = QLabel(
            "隐私边界：仅在按钮或快捷键触发时读取可见内容；不自动发送、不后台监听、不读取 WhatsApp 私有数据库。"
        )
        notice.setObjectName("mutedText")
        notice.setWordWrap(True)
        layout.addWidget(notice)

        capture_card = QFrame()
        capture_card.setObjectName("card")
        capture_layout = QGridLayout(capture_card)
        capture_layout.setContentsMargins(18, 16, 18, 16)
        capture_layout.setHorizontalSpacing(10)
        capture_layout.setVerticalSpacing(12)
        self.capture_button = QPushButton("捕获当前聊天")
        self.capture_button.setObjectName("primaryButton")
        self.capture_button.clicked.connect(self.capture_current_chat)
        capture_layout.addWidget(self.capture_button, 0, 0)
        self.screenshot_button = QPushButton("窗口截图 OCR")
        self.screenshot_button.clicked.connect(self.capture_screenshot)
        capture_layout.addWidget(self.screenshot_button, 0, 1)
        self.region_button = QPushButton("框选截图 OCR")
        self.region_button.clicked.connect(self.select_capture_region)
        capture_layout.addWidget(self.region_button, 0, 2)
        self.import_image_button = QPushButton("导入截图")
        self.import_image_button.clicked.connect(self.import_screenshot)
        capture_layout.addWidget(self.import_image_button, 0, 3)
        self.paste_button = QPushButton("粘贴聊天")
        self.paste_button.clicked.connect(self.paste_from_clipboard)
        capture_layout.addWidget(self.paste_button, 0, 4)

        capture_layout.addWidget(QLabel("全局快捷键"), 1, 0)
        self.hotkey_edit = QKeySequenceEdit()
        self.hotkey_edit.setObjectName("captureHotkey")
        self.hotkey_edit.setMinimumWidth(160)
        capture_layout.addWidget(self.hotkey_edit, 2, 0)
        capture_layout.addWidget(QLabel("最近消息数"), 1, 1)
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(20, 50)
        self.limit_spin.setValue(30)
        capture_layout.addWidget(self.limit_spin, 2, 1)
        self.uia_check = QCheckBox("启用 UI Automation")
        self.uia_check.setChecked(True)
        capture_layout.addWidget(self.uia_check, 1, 2, 2, 1)
        self.ocr_check = QCheckBox("启用 OCR 备用")
        self.ocr_check.setChecked(True)
        capture_layout.addWidget(self.ocr_check, 1, 3, 2, 1)
        self.browser_check = QCheckBox("允许 WhatsApp Web 浏览器窗口")
        capture_layout.addWidget(self.browser_check, 1, 4, 2, 1)
        self.save_settings_button = QPushButton("保存捕获设置")
        self.save_settings_button.clicked.connect(self.save_settings)
        capture_layout.addWidget(self.save_settings_button, 3, 0, 1, 2)
        self.platform_label = QLabel("Windows 支持全局快捷键和 UIA；其他平台可使用手动粘贴。")
        self.platform_label.setObjectName("mutedText")
        self.platform_label.setWordWrap(True)
        capture_layout.addWidget(self.platform_label, 3, 2, 1, 3)
        layout.addWidget(capture_card)

        customer_card = QFrame()
        customer_card.setObjectName("card")
        customer_layout = QGridLayout(customer_card)
        customer_layout.setContentsMargins(18, 14, 18, 14)
        customer_layout.addWidget(QLabel("关联客户"), 0, 0)
        self.customer_combo = QComboBox()
        self.customer_combo.setObjectName("captureCustomer")
        customer_layout.addWidget(self.customer_combo, 0, 1, 1, 3)
        self.new_customer_button = QPushButton("新建客户")
        self.new_customer_button.clicked.connect(self.add_customer)
        customer_layout.addWidget(self.new_customer_button, 0, 4)
        customer_layout.addWidget(QLabel("聊天标题"), 1, 0)
        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("captureTitle")
        self.title_edit.setPlaceholderText("可修改识别到的聊天标题")
        customer_layout.addWidget(self.title_edit, 1, 1, 1, 4)
        layout.addWidget(customer_card)

        manual_card = QFrame()
        manual_card.setObjectName("card")
        manual_layout = QVBoxLayout(manual_card)
        manual_layout.setContentsMargins(18, 14, 18, 14)
        manual_title = QLabel("手动粘贴 / 原始识别文本")
        manual_title.setObjectName("sectionHeading")
        manual_layout.addWidget(manual_title)
        self.raw_edit = QPlainTextEdit()
        self.raw_edit.setObjectName("rawChatInput")
        self.raw_edit.setPlaceholderText(
            "支持 WhatsApp 导出格式，也可使用：\n客户：Need quotation\n销售：I will confirm\n未知姓名的发送方会保留为“未知”。"
        )
        self.raw_edit.setMaximumHeight(130)
        manual_layout.addWidget(self.raw_edit)
        self.parse_button = QPushButton("解析并预览")
        self.parse_button.clicked.connect(self.parse_preview)
        manual_layout.addWidget(self.parse_button, 0, Qt.AlignRight)
        layout.addWidget(manual_card)

        preview_header = QHBoxLayout()
        preview_title = QLabel("消息预览（可编辑内容、修改发送方、删除敏感行）")
        preview_title.setObjectName("sectionHeading")
        preview_header.addWidget(preview_title)
        preview_header.addStretch(1)
        self.incomplete_label = QLabel("尚未捕获消息")
        self.incomplete_label.setObjectName("mutedText")
        preview_header.addWidget(self.incomplete_label)
        layout.addLayout(preview_header)

        self.message_table = QTableWidget(0, 6)
        self.message_table.setObjectName("captureMessagesTable")
        self.message_table.setHorizontalHeaderLabels(
            ["序号", "发送方", "消息内容", "消息时间", "来源", "置信度"]
        )
        self.message_table.verticalHeader().setVisible(False)
        self.message_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.message_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.message_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.message_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.message_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.message_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.message_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.message_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.message_table.setAlternatingRowColors(True)
        self.message_table.setMinimumHeight(230)
        layout.addWidget(self.message_table)

        actions = QHBoxLayout()
        self.delete_message_button = QPushButton("删除选中消息")
        self.delete_message_button.clicked.connect(self.delete_selected_message)
        actions.addWidget(self.delete_message_button)
        actions.addStretch(1)
        self.save_button = QPushButton("确认保存到本地")
        self.save_button.setObjectName("primaryButton")
        self.save_button.clicked.connect(self.save_capture)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)
        self.status_label = QLabel("请主动捕获或粘贴聊天；保存前请逐条核对。")
        self.status_label.setObjectName("mutedText")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _load_settings(self) -> None:
        sequence = self.settings.get("capture_hotkey", "Ctrl+Shift+A")
        self.hotkey_edit.setKeySequence(QKeySequence(sequence))
        try:
            limit = int(self.settings.get("capture_message_limit", "30"))
        except ValueError:
            limit = 30
        self.limit_spin.setValue(min(50, max(20, limit)))
        self.uia_check.setChecked(self.settings.get("capture_uia_enabled", "1") == "1")
        self.ocr_check.setChecked(self.settings.get("capture_ocr_enabled", "1") == "1")
        self.browser_check.setChecked(self.settings.get("capture_allow_browser", "0") == "1")

    def save_settings(self) -> bool:
        sequence = self.hotkey_edit.keySequence().toString(QKeySequence.PortableText)
        try:
            normalized = parse_hotkey(sequence).normalized
        except ValueError as exc:
            self._set_status(str(exc))
            return False
        values = {
            "capture_hotkey": normalized,
            "capture_message_limit": str(self.limit_spin.value()),
            "capture_uia_enabled": str(int(self.uia_check.isChecked())),
            "capture_ocr_enabled": str(int(self.ocr_check.isChecked())),
            "capture_allow_browser": str(int(self.browser_check.isChecked())),
        }
        try:
            for key, value in values.items():
                self.settings.set(key, value)
        except sqlite3.Error:
            logger.exception("保存捕获设置失败")
            self._set_status("捕获设置保存失败，请稍后重试。")
            return False
        self.hotkey_edit.setKeySequence(QKeySequence(normalized))
        self.hotkey_changed.emit(normalized)
        self._set_status("捕获设置已保存。")
        return True

    def refresh_customers(self) -> None:
        selected_id = self.customer_combo.currentData()
        customers = self.customer_service.list()
        self.customer_combo.blockSignals(True)
        self.customer_combo.clear()
        self.customer_combo.addItem("请选择已有客户", None)
        for customer in customers:
            company = f" · {customer.company_name}" if customer.company_name else ""
            self.customer_combo.addItem(f"{customer.name}{company}", customer.id)
        index = self.customer_combo.findData(selected_id)
        self.customer_combo.setCurrentIndex(index if index >= 0 else 0)
        self.customer_combo.blockSignals(False)

    def add_customer(self) -> None:
        dialog = CustomerEditDialog(parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            customer = self.customer_service.create(dialog.data())
        except Exception as exc:
            self._show_error("新建客户失败", exc)
            return
        self.refresh_customers()
        self.customer_combo.setCurrentIndex(self.customer_combo.findData(customer.id))
        self.customers_changed.emit()
        self._set_status(f"已新建并选择客户：{customer.name}")

    def capture_current_chat(self) -> None:
        options = {
            "use_uia": self.uia_check.isChecked(),
            "use_ocr": self.ocr_check.isChecked(),
            "allow_browser": self.browser_check.isChecked(),
            "limit": self.limit_spin.value(),
        }
        self._run_capture(lambda: self.capture_service.capture_current(**options))

    def capture_screenshot(self) -> None:
        def capture():
            window = self.capture_service.get_target_window(self.browser_check.isChecked())
            return self.capture_service.capture_window_ocr(window, limit=self.limit_spin.value())

        self._run_capture(capture)

    def select_capture_region(self) -> None:
        try:
            window = self.capture_service.get_target_window(self.browser_check.isChecked())
        except Exception as exc:
            self._show_error("窗口识别失败", exc)
            return
        selector = RegionSelectorDialog(self)
        if selector.exec() != QDialog.Accepted:
            return
        bounds = selector.selected_bounds()
        selector.hide()
        QApplication.processEvents()
        if bounds is None:
            self._set_status("未选择有效截图区域。")
            return
        self._run_capture(
            lambda: self.capture_service.capture_window_ocr(
                window, bounds=bounds, limit=self.limit_spin.value()
            )
        )

    def import_screenshot(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "导入聊天截图",
            str(Path.home()),
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if path:
            self._run_capture(
                lambda: self.capture_service.recognize_image(path, limit=self.limit_spin.value())
            )

    def paste_from_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        if not text.strip():
            self._set_status("剪贴板没有文本，请先复制 WhatsApp 可见聊天内容。")
            return
        self.raw_edit.setPlainText(text)
        self.parse_preview()

    def parse_preview(self) -> None:
        customer = self.customer_service.get(self.customer_combo.currentData()) if self.customer_combo.currentData() else None
        messages = MessageParser.parse(
            self.raw_edit.toPlainText(),
            customer_name=customer.name if customer else "",
        )
        if not messages:
            self._set_status("没有可预览的消息，请粘贴包含文字的聊天内容。")
            return
        title = self.title_edit.text().strip() or (customer.name if customer else "手动粘贴聊天")
        self.load_result(
            CaptureResult(
                title=title,
                window_title="手动粘贴",
                source="manual",
                messages=messages,
                may_be_incomplete=True,
                warning="手动粘贴内容仅包含用户提供的文本，可能不完整。",
            )
        )

    def load_result(self, result: CaptureResult) -> None:
        self.current_source = result.source
        self.may_be_incomplete = result.may_be_incomplete
        self.title_edit.setText(result.title)
        self._populate_messages(result.messages)
        self.incomplete_label.setText(
            "可见消息，可能不完整" if result.may_be_incomplete else "完整性未标记"
        )
        self.incomplete_label.setToolTip(result.warning)
        self._set_status(f"已预览 {len(result.messages)} 条消息。{result.warning}")
        self.result_ready.emit()

    def _populate_messages(self, messages: list[CapturedMessage]) -> None:
        self.message_table.setRowCount(len(messages))
        for row, message in enumerate(messages):
            number = QTableWidgetItem(str(row + 1))
            number.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.message_table.setItem(row, 0, number)

            sender = QComboBox()
            for label, value in _SENDER_LABELS:
                sender.addItem(label, value)
            sender.setCurrentIndex(sender.findData(message.sender_type))
            self.message_table.setCellWidget(row, 1, sender)

            content = QTableWidgetItem(message.content)
            content.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            content.setData(_RECOGNIZED_AT_ROLE, message.recognized_at)
            content.setData(_CONFIDENCE_ROLE, message.confidence)
            content.setData(_SENDER_NAME_ROLE, message.sender_name)
            content.setToolTip(message.content)
            self.message_table.setItem(row, 2, content)

            timestamp = QTableWidgetItem(message.timestamp or "未知")
            timestamp.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            timestamp.setData(Qt.UserRole, message.timestamp)
            self.message_table.setItem(row, 3, timestamp)
            source = QTableWidgetItem(_SOURCE_LABELS[message.source])
            source.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            source.setData(Qt.UserRole, message.source)
            self.message_table.setItem(row, 4, source)
            confidence = QTableWidgetItem(
                "—" if message.confidence is None else f"{message.confidence:.0%}"
            )
            confidence.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.message_table.setItem(row, 5, confidence)
            self.message_table.setRowHeight(row, 44)

    def current_messages(self) -> list[CapturedMessage]:
        messages = []
        for row in range(self.message_table.rowCount()):
            content_item = self.message_table.item(row, 2)
            content = content_item.text().strip()
            if not content:
                raise ConversationValidationError(f"第 {row + 1} 条消息为空，请编辑或删除该行。")
            sender = self.message_table.cellWidget(row, 1)
            messages.append(
                CapturedMessage(
                    content=content,
                    sender_type=sender.currentData(),
                    timestamp=self.message_table.item(row, 3).data(Qt.UserRole),
                    source=self.message_table.item(row, 4).data(Qt.UserRole),
                    recognized_at=content_item.data(_RECOGNIZED_AT_ROLE),
                    confidence=content_item.data(_CONFIDENCE_ROLE),
                    sender_name=content_item.data(_SENDER_NAME_ROLE),
                )
            )
        return messages

    def delete_selected_message(self) -> None:
        row = self.message_table.currentRow()
        if row >= 0:
            self.message_table.removeRow(row)
            for index in range(self.message_table.rowCount()):
                self.message_table.item(index, 0).setText(str(index + 1))
            self._set_status("已从本次预览删除选中消息；尚未保存时不影响原聊天。")

    def save_capture(self) -> bool:
        customer_id = self.customer_combo.currentData()
        if customer_id is None:
            self._set_status("请先选择客户，再确认保存。")
            return False
        try:
            messages = self.current_messages()
            if not messages:
                raise ConversationValidationError("至少一条消息才能保存")
            self.conversation_service.save_capture(
                customer_id,
                self.title_edit.text(),
                messages,
                source=self.current_source,
                may_be_incomplete=self.may_be_incomplete,
            )
        except (ConversationValidationError, ValueError) as exc:
            self._set_status(str(exc))
            return False
        except sqlite3.Error:
            logger.exception("保存捕获聊天失败")
            self._set_status("本地数据库保存失败，请稍后重试。")
            return False
        message = f"已保存 {len(messages)} 条消息到本地客户记录；未调用 AI，未发送 WhatsApp 消息。"
        self._set_status(message)
        return True

    def _run_capture(self, operation) -> None:
        self.capture_button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = operation()
            self.load_result(result)
        except Exception as exc:
            self._show_error("捕获失败", exc)
        finally:
            QApplication.restoreOverrideCursor()
            self.capture_button.setEnabled(True)

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_message.emit(message)

    def _show_error(self, title: str, error: Exception) -> None:
        logger.error("%s：%s", title, error)
        detail = str(error) if isinstance(error, (CaptureError, ValueError)) else "操作未完成，请重试或改用手动粘贴。"
        self._set_status(f"{title}：{detail}")
        QMessageBox.critical(self, title, f"{detail}\n\n现有预览内容已保留。")
