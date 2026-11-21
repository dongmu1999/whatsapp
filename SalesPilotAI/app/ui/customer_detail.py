"""客户新增/编辑表单和只读详情对话框。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.models.customer import (
    CUSTOMER_FIELDS,
    Customer,
    CustomerValidationError,
    FIELD_LABELS,
    SALES_STAGES,
    normalize_customer_data,
)

_LINE_FIELDS = (
    "name",
    "company_name",
    "country",
    "contact_info",
    "whatsapp_number",
    "email",
    "website",
    "customer_type",
    "interested_products",
    "expected_quantity",
    "target_price",
    "first_contact_at",
    "last_contact_at",
    "next_followup_at",
)
_MULTILINE_FIELDS = ("historical_quotes", "purchase_history", "core_concerns", "notes")
_FORM_ORDER = (
    "name",
    "company_name",
    "country",
    "contact_info",
    "whatsapp_number",
    "email",
    "website",
    "customer_type",
    "interested_products",
    "expected_quantity",
    "target_price",
    "sales_stage",
    "intent_score",
    "historical_quotes",
    "purchase_history",
    "core_concerns",
    "notes",
    "first_contact_at",
    "last_contact_at",
    "next_followup_at",
)


class CustomerEditDialog(QDialog):
    def __init__(self, customer: Customer | None = None, parent=None):
        super().__init__(parent)
        self.customer = customer
        self.fields: dict[str, QWidget] = {}
        self.setObjectName("customerEditDialog")
        self.setWindowTitle("编辑客户" if customer else "新增客户")
        self.setModal(True)
        self.resize(640, 680)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 20)
        outer.setSpacing(12)
        heading = QLabel(self.windowTitle())
        heading.setObjectName("pageHeading")
        outer.addWidget(heading)
        hint = QLabel("带 * 为必填项。时间留空或填写 UTC ISO 时间，例如 2026-11-21T09:30:00Z。")
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        form = QFormLayout(content)
        form.setContentsMargins(4, 4, 12, 8)
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        for field in _FORM_ORDER:
            if field in _LINE_FIELDS:
                widget = QLineEdit()
                widget.setObjectName(f"customer_{field}")
                if field == "name":
                    widget.setMaxLength(200)
                if field.endswith("_at"):
                    widget.setPlaceholderText("2026-11-21T09:30:00Z")
            elif field in _MULTILINE_FIELDS:
                widget = QPlainTextEdit()
                widget.setObjectName(f"customer_{field}")
                widget.setMinimumHeight(76)
                widget.setMaximumHeight(120)
            elif field == "sales_stage":
                widget = QComboBox()
                widget.setObjectName("customer_sales_stage")
                for stage in SALES_STAGES:
                    widget.addItem(stage, stage)
            else:
                widget = QSpinBox()
                widget.setObjectName("customer_intent_score")
                widget.setRange(0, 100)
                widget.setSuffix(" 分")
                widget.setSpecialValueText("0 分")
            self.fields[field] = widget
            label = FIELD_LABELS[field] + (" *" if field == "name" else "")
            form.addRow(label, widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("保存客户")
        buttons.button(QDialogButtonBox.Save).setObjectName("primaryButton")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        if customer is not None:
            self._set_values(customer)

    def _set_values(self, customer: Customer) -> None:
        values = customer.as_dict()
        for field, widget in self.fields.items():
            value = values.get(field)
            if isinstance(widget, QLineEdit):
                widget.setText("" if value is None else str(value))
            elif isinstance(widget, QPlainTextEdit):
                widget.setPlainText("" if value is None else str(value))
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(max(0, widget.findData(value)))
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(value or 0))

    def data(self) -> dict:
        raw = {}
        for field, widget in self.fields.items():
            if isinstance(widget, QLineEdit):
                raw[field] = widget.text()
            elif isinstance(widget, QPlainTextEdit):
                raw[field] = widget.toPlainText()
            elif isinstance(widget, QComboBox):
                raw[field] = widget.currentData()
            elif isinstance(widget, QSpinBox):
                raw[field] = widget.value()
        return normalize_customer_data(raw)

    def accept(self) -> None:
        try:
            self.data()
        except CustomerValidationError as exc:
            QMessageBox.warning(self, "无法保存客户", str(exc))
            return
        super().accept()


class CustomerDetailDialog(QDialog):
    def __init__(self, customer: Customer, parent=None):
        super().__init__(parent)
        self.customer = customer
        self.field_values: dict[str, QLabel] = {}
        self.setObjectName("customerDetailDialog")
        self.setWindowTitle(f"客户详情 · {customer.name}")
        self.setModal(True)
        self.resize(680, 640)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(12)
        heading = QLabel(customer.name)
        heading.setObjectName("pageHeading")
        outer.addWidget(heading)
        subtitle = QLabel(f"{customer.company_name or '未填写公司'} · {customer.sales_stage} · 意向评分 {customer.intent_score}")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        form = QFormLayout(content)
        form.setContentsMargins(4, 4, 12, 8)
        form.setHorizontalSpacing(22)
        form.setVerticalSpacing(13)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        values = customer.as_dict()
        for field in CUSTOMER_FIELDS:
            value = values.get(field)
            label = QLabel("—" if value is None or value == "" else str(value))
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            label.setObjectName(f"detail_{field}")
            self.field_values[field] = label
            form.addRow(FIELD_LABELS[field], label)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText("关闭")
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
