"""跟进任务：本地创建、筛选、结果记录与完成/取消。"""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QDate, QTime, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.followup import (
    PRIORITIES,
    PRIORITY_LABELS,
    STATUS_LABELS,
    FollowupValidationError,
)
from app.services.customer_service import CustomerService
from app.services.followup_service import FollowupService

_STATUS_FILTERS = (("全部状态", None), ("待办", "pending"), ("已完成", "completed"), ("已取消", "cancelled"))


class FollowupPage(QWidget):
    status_message = Signal(str)
    followups_changed = Signal()

    def __init__(
        self,
        followup_service: FollowupService,
        customer_service: CustomerService,
        parent=None,
    ):
        super().__init__(parent)
        self.followup_service = followup_service
        self.customer_service = customer_service
        self.setObjectName("followupPage")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)
        content = QWidget()
        content.setObjectName("pageContent")
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)

        heading = QLabel("跟进任务")
        heading.setObjectName("pageHeading")
        layout.addWidget(heading)
        subtitle = QLabel(
            "在本地安排和记录客户跟进。提醒只在软件内显示，不会自动发送 WhatsApp 消息。"
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addWidget(self._build_create_card())
        layout.addWidget(self._build_list_card())

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.refresh_customers()
        self.refresh()

    def _build_create_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        title = QLabel("新建跟进任务")
        title.setObjectName("sectionHeading")
        layout.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.customer_combo = QComboBox()
        self.customer_combo.setMinimumWidth(180)
        row.addWidget(self.customer_combo, 2)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())
        row.addWidget(self.date_edit)
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        now = datetime.now().astimezone() + timedelta(hours=1)
        self.time_edit.setTime(QTime(now.hour, now.minute))
        row.addWidget(self.time_edit)
        self.priority_combo = QComboBox()
        for priority in PRIORITIES:
            self.priority_combo.addItem(PRIORITY_LABELS[priority], priority)
        self.priority_combo.setCurrentIndex(self.priority_combo.findData("medium"))
        row.addWidget(self.priority_combo)
        layout.addLayout(row)

        self.reason_edit = QLineEdit()
        self.reason_edit.setPlaceholderText("跟进原因，例如：报价后确认客户反馈")
        layout.addWidget(self.reason_edit)
        self.content_edit = QPlainTextEdit()
        self.content_edit.setPlaceholderText("跟进内容，例如：礼貌确认是否收到报价并询问是否需要补充资料")
        self.content_edit.setMaximumHeight(84)
        layout.addWidget(self.content_edit)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.create_task_button = QPushButton("创建跟进任务")
        self.create_task_button.setObjectName("primaryButton")
        self.create_task_button.setCursor(Qt.PointingHandCursor)
        self.create_task_button.clicked.connect(self.create_task)
        actions.addWidget(self.create_task_button)
        layout.addLayout(actions)
        return card

    def _build_list_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("任务列表")
        title.setObjectName("sectionHeading")
        header.addWidget(title)
        header.addStretch(1)
        self.status_filter_combo = QComboBox()
        for label, value in _STATUS_FILTERS:
            self.status_filter_combo.addItem(label, value)
        self.status_filter_combo.currentIndexChanged.connect(lambda _: self.refresh())
        header.addWidget(self.status_filter_combo)
        self.customer_filter_combo = QComboBox()
        self.customer_filter_combo.setMinimumWidth(160)
        self.customer_filter_combo.currentIndexChanged.connect(lambda _: self.refresh())
        header.addWidget(self.customer_filter_combo)
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refresh)
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        self.task_table = QTableWidget(0, 8)
        self.task_table.setObjectName("followupTaskTable")
        self.task_table.setHorizontalHeaderLabels(
            ["客户", "计划时间", "优先级", "跟进原因", "跟进内容", "跟进结果", "状态", "逾期"]
        )
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.task_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.task_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.task_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.task_table.setAlternatingRowColors(True)
        self.task_table.setShowGrid(False)
        self.task_table.setMinimumHeight(220)
        layout.addWidget(self.task_table)

        actions = QHBoxLayout()
        self.record_button = QPushButton("记录跟进结果")
        self.record_button.clicked.connect(lambda: self.record_selected_result())
        actions.addWidget(self.record_button)
        self.complete_button = QPushButton("完成并保存结果")
        self.complete_button.setObjectName("primaryButton")
        self.complete_button.clicked.connect(lambda: self.complete_selected())
        actions.addWidget(self.complete_button)
        self.cancel_button = QPushButton("取消任务")
        self.cancel_button.setObjectName("dangerButton")
        self.cancel_button.clicked.connect(self.cancel_selected)
        actions.addWidget(self.cancel_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        return card

    def refresh_customers(self) -> None:
        customers = self.customer_service.list()
        selected = self.customer_combo.currentData()
        filter_selected = self.customer_filter_combo.currentData()
        self.customer_combo.blockSignals(True)
        self.customer_filter_combo.blockSignals(True)
        self.customer_combo.clear()
        self.customer_filter_combo.clear()
        self.customer_combo.addItem("请选择客户", None)
        self.customer_filter_combo.addItem("全部客户", None)
        for customer in customers:
            company = f" · {customer.company_name}" if customer.company_name else ""
            label = f"{customer.name}{company}"
            self.customer_combo.addItem(label, customer.id)
            self.customer_filter_combo.addItem(label, customer.id)
        customer_index = self.customer_combo.findData(selected)
        filter_index = self.customer_filter_combo.findData(filter_selected)
        self.customer_combo.setCurrentIndex(customer_index if customer_index >= 0 else 0)
        self.customer_filter_combo.setCurrentIndex(
            filter_index if filter_index >= 0 else 0
        )
        self.customer_combo.blockSignals(False)
        self.customer_filter_combo.blockSignals(False)

    def refresh(self) -> None:
        tasks = self.followup_service.list(
            customer_id=self.customer_filter_combo.currentData(),
            status=self.status_filter_combo.currentData(),
        )
        self.task_table.setRowCount(0)
        for row, task in enumerate(tasks):
            self.task_table.insertRow(row)
            name_item = QTableWidgetItem(task.customer_name)
            name_item.setData(Qt.UserRole, task.id)
            self.task_table.setItem(row, 0, name_item)
            self.task_table.setItem(row, 1, QTableWidgetItem(task.due_local_text))
            self.task_table.setItem(
                row, 2, QTableWidgetItem(PRIORITY_LABELS.get(task.priority, task.priority))
            )
            self.task_table.setItem(row, 3, QTableWidgetItem(task.reason or "—"))
            self.task_table.setItem(row, 4, QTableWidgetItem(task.content))
            self.task_table.setItem(row, 5, QTableWidgetItem(task.result or "—"))
            self.task_table.setItem(
                row, 6, QTableWidgetItem(STATUS_LABELS.get(task.status, task.status))
            )
            overdue = task.is_overdue()
            overdue_item = QTableWidgetItem("逾期" if overdue else "—")
            if overdue:
                overdue_item.setForeground(QColor("#c0392b"))
            self.task_table.setItem(row, 7, overdue_item)
            for column in range(8):
                item = self.task_table.item(row, column)
                item.setToolTip(item.text())

    def create_task(self) -> bool:
        customer_id = self.customer_combo.currentData()
        if customer_id is None:
            self._set_status("请选择客户后再创建跟进任务。")
            return False
        date = self.date_edit.date()
        time = self.time_edit.time()
        due = datetime(
            date.year(), date.month(), date.day(), time.hour(), time.minute()
        ).astimezone()
        try:
            task = self.followup_service.create(
                customer_id,
                due,
                self.reason_edit.text(),
                self.priority_combo.currentData(),
                self.content_edit.toPlainText(),
            )
        except FollowupValidationError as exc:
            self._set_status(str(exc))
            return False
        self.content_edit.clear()
        self.reason_edit.clear()
        self.refresh()
        self._set_status(
            f"已创建跟进任务（{task.customer_name}，{task.due_local_text}）；仅本地提醒，不会发送 WhatsApp 消息。"
        )
        self.followups_changed.emit()
        return True

    def prefill(
        self,
        customer_id: int,
        due_days: int,
        content: str,
        reason: str = "AI 建议跟进",
    ) -> None:
        """把 AI 建议填入表单，仍由用户核对后手动创建。"""
        if self.customer_combo.findData(customer_id) < 0:
            self.refresh_customers()
        index = self.customer_combo.findData(customer_id)
        if index < 0:
            return
        self.customer_combo.setCurrentIndex(index)
        target = datetime.now().astimezone() + timedelta(days=max(int(due_days), 0))
        self.date_edit.setDate(QDate(target.year, target.month, target.day))
        self.time_edit.setTime(QTime(target.hour, target.minute))
        self.reason_edit.setText(reason)
        self.content_edit.setPlainText(content)
        self._set_status("已填入 AI 跟进建议，请核对客户和时间后手动创建。")

    def find_task_row(self, task_id: int) -> int:
        for row in range(self.task_table.rowCount()):
            item = self.task_table.item(row, 0)
            if item is not None and item.data(Qt.UserRole) == task_id:
                return row
        return -1

    def select_task(self, task_id: int) -> bool:
        row = self.find_task_row(task_id)
        if row < 0:
            return False
        self.task_table.selectRow(row)
        return True

    def selected_task_id(self) -> int | None:
        row = self.task_table.currentRow()
        if row < 0:
            return None
        item = self.task_table.item(row, 0)
        return None if item is None else item.data(Qt.UserRole)

    def record_selected_result(self, result: str | None = None) -> bool:
        task_id = self.selected_task_id()
        if task_id is None:
            self._set_status("请先选择一条待办跟进任务。")
            return False
        if result is None:
            result, accepted = QInputDialog.getMultiLineText(
                self, "记录跟进结果", "本次跟进结果："
            )
            if not accepted:
                return False
        try:
            task = self.followup_service.record_result(task_id, result)
        except FollowupValidationError as exc:
            self._set_status(str(exc))
            return False
        self.refresh()
        self._set_status(f"已记录 {task.customer_name} 的跟进结果，任务仍保持待办。")
        self.followups_changed.emit()
        return True

    def complete_selected(self, result: str | None = None) -> bool:
        task_id = self.selected_task_id()
        if task_id is None:
            self._set_status("请先选择一条待办跟进任务。")
            return False
        if result is None:
            result, accepted = QInputDialog.getMultiLineText(
                self, "完成跟进任务", "跟进结果（可选）："
            )
            if not accepted:
                return False
        try:
            task = self.followup_service.complete(task_id, result)
        except FollowupValidationError as exc:
            self._set_status(str(exc))
            return False
        self.refresh()
        self._set_status(f"已完成 {task.customer_name} 的跟进任务；未发送任何 WhatsApp 消息。")
        self.followups_changed.emit()
        return True

    def cancel_selected(self) -> bool:
        task_id = self.selected_task_id()
        if task_id is None:
            self._set_status("请先选择一条待办跟进任务。")
            return False
        try:
            task = self.followup_service.cancel(task_id)
        except FollowupValidationError as exc:
            self._set_status(str(exc))
            return False
        self.refresh()
        self._set_status(f"已取消 {task.customer_name} 的跟进任务。")
        self.followups_changed.emit()
        return True

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_message.emit(message)
