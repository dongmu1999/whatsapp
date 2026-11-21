"""客户管理页面：列表、搜索筛选、详情、编辑和导入导出。"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.customer import Customer, SALES_STAGES
from app.services.customer_service import CustomerService
from app.ui.customer_detail import CustomerDetailDialog, CustomerEditDialog

logger = logging.getLogger(__name__)


def _format_time(value: str | None) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone()
        return parsed.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


class CustomerPage(QWidget):
    customers_changed = Signal()
    status_message = Signal(str)

    def __init__(self, service: CustomerService, parent=None):
        super().__init__(parent)
        self.service = service
        self.current_customers: list[Customer] = []
        self.descending = True
        self.setObjectName("customerPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title_group = QVBoxLayout()
        title_group.setSpacing(4)
        title = QLabel("客户管理")
        title.setObjectName("pageHeading")
        title_group.addWidget(title)
        subtitle = QLabel("维护本地客户档案，按销售阶段和沟通进展快速定位客户。")
        subtitle.setObjectName("pageSubtitle")
        title_group.addWidget(subtitle)
        header.addLayout(title_group)
        header.addStretch(1)

        self.import_button = QPushButton("导入客户")
        self.import_button.setObjectName("importCustomersButton")
        self.import_button.clicked.connect(self.import_customers)
        header.addWidget(self.import_button, 0, Qt.AlignTop)
        self.export_button = QPushButton("导出客户")
        self.export_button.setObjectName("exportCustomersButton")
        self.export_button.clicked.connect(self.export_customers)
        header.addWidget(self.export_button, 0, Qt.AlignTop)
        self.add_button = QPushButton("新增客户")
        self.add_button.setObjectName("primaryButton")
        self.add_button.clicked.connect(self.add_customer)
        header.addWidget(self.add_button, 0, Qt.AlignTop)
        layout.addLayout(header)

        filter_card = QFrame()
        filter_card.setObjectName("card")
        filters = QGridLayout(filter_card)
        filters.setContentsMargins(16, 14, 16, 14)
        filters.setHorizontalSpacing(10)
        filters.setVerticalSpacing(10)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("customerSearch")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setPlaceholderText("搜索姓名、公司、联系方式、WhatsApp、邮箱或感兴趣产品")
        self.search_edit.textChanged.connect(self.refresh)
        filters.addWidget(self.search_edit, 0, 0, 1, 4)

        self.country_combo = QComboBox()
        self.country_combo.setObjectName("customerCountryFilter")
        self.country_combo.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.country_combo, 1, 0)

        self.stage_combo = QComboBox()
        self.stage_combo.setObjectName("customerStageFilter")
        self.stage_combo.addItem("全部阶段", "")
        for stage in SALES_STAGES:
            self.stage_combo.addItem(stage, stage)
        self.stage_combo.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.stage_combo, 1, 1)

        self.sort_combo = QComboBox()
        self.sort_combo.setObjectName("customerSort")
        self.sort_combo.addItem("按最近沟通", "last_contact")
        self.sort_combo.addItem("按意向评分", "intent_score")
        self.sort_combo.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.sort_combo, 1, 2)

        self.sort_order_button = QPushButton("降序")
        self.sort_order_button.setObjectName("customerSortOrder")
        self.sort_order_button.setToolTip("切换升序或降序")
        self.sort_order_button.clicked.connect(self.toggle_sort_order)
        filters.addWidget(self.sort_order_button, 1, 3)
        filters.setColumnStretch(0, 2)
        filters.setColumnStretch(1, 2)
        filters.setColumnStretch(2, 2)
        filters.setColumnStretch(3, 1)
        layout.addWidget(filter_card)

        action_row = QHBoxLayout()
        self.count_label = QLabel()
        self.count_label.setObjectName("mutedText")
        action_row.addWidget(self.count_label)
        action_row.addStretch(1)
        self.detail_button = QPushButton("查看详情")
        self.detail_button.setObjectName("customerDetailButton")
        self.detail_button.clicked.connect(self.show_selected_detail)
        action_row.addWidget(self.detail_button)
        self.edit_button = QPushButton("编辑")
        self.edit_button.setObjectName("customerEditButton")
        self.edit_button.clicked.connect(self.edit_selected)
        action_row.addWidget(self.edit_button)
        self.delete_button = QPushButton("删除")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self.delete_selected)
        action_row.addWidget(self.delete_button)
        layout.addLayout(action_row)

        table_card = QFrame()
        table_card.setObjectName("card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(0, 0, 0, 0)
        self.table_stack = QStackedWidget()
        self.table = QTableWidget(0, 8)
        self.table.setObjectName("customersTable")
        self.table.setHorizontalHeaderLabels(
            ["客户姓名", "公司名称", "国家", "WhatsApp", "销售阶段", "意向评分", "最近沟通", "下次跟进"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(280)
        self.table.itemSelectionChanged.connect(self._update_action_state)
        self.table.cellDoubleClicked.connect(lambda *_: self.show_selected_detail())
        self.table_stack.addWidget(self.table)

        self.empty_label = QLabel("暂无客户。点击“新增客户”或“导入客户”开始建立本地客户档案。")
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setMinimumHeight(280)
        self.table_stack.addWidget(self.empty_label)
        table_layout.addWidget(self.table_stack)
        layout.addWidget(table_card, 1)

        self._update_action_state()
        self.refresh()

    def refresh(self) -> None:
        try:
            country = self.country_combo.currentData() or ""
            search = self.search_edit.text()
            stage = self.stage_combo.currentData() or ""
            self.current_customers = self.service.list(
                search=search,
                country=country,
                sales_stage=stage,
                sort_by=self.sort_combo.currentData(),
                descending=self.descending,
            )
            self._refresh_countries()
            self._populate_table()
            filtered = bool(search.strip() or country or stage)
            self.count_label.setText(
                f"找到 {len(self.current_customers)} 位客户" if filtered else f"共 {len(self.current_customers)} 位客户"
            )
            if filtered and not self.current_customers:
                self.empty_label.setText("没有找到符合条件的客户，请调整搜索或筛选条件。")
            else:
                self.empty_label.setText("暂无客户。点击“新增客户”或“导入客户”开始建立本地客户档案。")
            self.table_stack.setCurrentWidget(self.table if self.current_customers else self.empty_label)
        except Exception as exc:
            self._show_error("客户列表加载失败", exc)

    def _refresh_countries(self) -> None:
        selected = self.country_combo.currentData() or ""
        countries = self.service.countries()
        self.country_combo.blockSignals(True)
        self.country_combo.clear()
        self.country_combo.addItem("全部国家", "")
        for country in countries:
            self.country_combo.addItem(country, country)
        index = self.country_combo.findData(selected)
        self.country_combo.setCurrentIndex(index if index >= 0 else 0)
        self.country_combo.blockSignals(False)

    def _populate_table(self) -> None:
        selected_id = self._selected_customer_id()
        self.table.setRowCount(len(self.current_customers))
        selected_row = -1
        for row, customer in enumerate(self.current_customers):
            values = (
                customer.name,
                customer.company_name or "—",
                customer.country or "—",
                customer.whatsapp_number or customer.contact_info or "—",
                customer.sales_stage,
                str(customer.intent_score),
                _format_time(customer.last_contact_at),
                _format_time(customer.next_followup_at),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                item.setData(Qt.UserRole, customer.id)
                if column == 5:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, column, item)
            if customer.id == selected_id:
                selected_row = row
        if selected_row >= 0:
            self.table.selectRow(selected_row)
        self._update_action_state()

    def _selected_customer_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return int(item.data(Qt.UserRole)) if item is not None else None

    def selected_customer(self) -> Customer | None:
        customer_id = self._selected_customer_id()
        return self.service.get(customer_id) if customer_id is not None else None

    def _update_action_state(self) -> None:
        enabled = self._selected_customer_id() is not None
        self.detail_button.setEnabled(enabled)
        self.edit_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)

    def toggle_sort_order(self) -> None:
        self.descending = not self.descending
        self.sort_order_button.setText("降序" if self.descending else "升序")
        self.refresh()

    def add_customer(self) -> None:
        dialog = CustomerEditDialog(parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            customer = self.service.create(dialog.data())
        except Exception as exc:
            self._show_error("新增客户失败", exc)
            return
        self._after_change(f"已保存客户：{customer.name}")

    def edit_selected(self) -> None:
        customer = self.selected_customer()
        if customer is None:
            return
        dialog = CustomerEditDialog(customer, self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            updated = self.service.update(customer.id, dialog.data())
        except Exception as exc:
            self._show_error("编辑客户失败", exc)
            return
        self._after_change(f"已更新客户：{updated.name}")

    def show_selected_detail(self) -> None:
        customer = self.selected_customer()
        if customer is not None:
            CustomerDetailDialog(customer, self).exec()

    def delete_selected(self) -> None:
        customer = self.selected_customer()
        if customer is None:
            return
        answer = QMessageBox.warning(
            self,
            "确认删除客户",
            f"确定删除客户“{customer.name}”吗？\n\n该客户的聊天记录、分析、记忆和跟进任务也会一并删除，且无法撤销。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.service.delete(customer.id)
        except Exception as exc:
            self._show_error("删除客户失败", exc)
            return
        self._after_change(f"已删除客户：{customer.name}")

    def import_customers(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "导入客户",
            str(Path.home()),
            "客户文件 (*.csv *.xlsx *.xlsm);;CSV 文件 (*.csv);;Excel 文件 (*.xlsx *.xlsm)",
        )
        if not path:
            return
        try:
            result = self.service.import_file(path)
        except Exception as exc:
            self._show_error("客户导入失败", exc)
            return
        self.refresh()
        if result.imported:
            self.customers_changed.emit()
        message = f"导入完成：成功 {result.imported} 条，失败 {result.failed} 条。"
        if result.errors:
            details = "\n".join(result.errors[:8])
            if len(result.errors) > 8:
                details += f"\n另有 {len(result.errors) - 8} 条错误未显示。"
            message += f"\n\n{details}"
        QMessageBox.information(self, "客户导入结果", message)
        self.status_message.emit(message.splitlines()[0])

    def export_customers(self) -> None:
        if not self.current_customers:
            QMessageBox.information(self, "导出客户", "当前没有可导出的客户。")
            return
        default_name = f"客户档案_{datetime.now():%Y%m%d}.xlsx"
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "导出当前客户列表",
            str(Path.home() / default_name),
            "Excel 文件 (*.xlsx);;CSV 文件 (*.csv)",
        )
        if not path:
            return
        if not Path(path).suffix:
            path += ".csv" if selected_filter.startswith("CSV") else ".xlsx"
        try:
            count = self.service.export_file(path, self.current_customers)
        except Exception as exc:
            self._show_error("客户导出失败", exc)
            return
        self.status_message.emit(f"已导出 {count} 位客户：{path}")
        QMessageBox.information(self, "导出完成", f"已导出当前列表中的 {count} 位客户。\n\n{path}")

    def _after_change(self, message: str) -> None:
        self.refresh()
        self.customers_changed.emit()
        self.status_message.emit(message)

    def _show_error(self, title: str, error: Exception) -> None:
        logger.exception("%s", title, exc_info=error)
        message = "本地数据库操作失败，请稍后重试。" if isinstance(error, sqlite3.Error) else str(error)
        QMessageBox.critical(self, title, message)
