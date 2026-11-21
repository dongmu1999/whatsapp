"""产品知识库：文档导入、分类、全文搜索、内容预览与产品资料维护。"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.knowledge import (
    FILE_TYPE_LABELS,
    KnowledgeError,
)

logger = logging.getLogger(__name__)

_IMPORT_FILTER = (
    "支持的知识库文件 (*.pdf *.docx *.xlsx *.csv *.txt *.md *.markdown);;"
    "PDF (*.pdf);;Word (*.docx);;Excel (*.xlsx);;CSV (*.csv);;"
    "文本 (*.txt);;Markdown (*.md *.markdown)"
)

_PRODUCT_FIELDS = (
    ("name", "产品名称 *"),
    ("model", "型号"),
    ("category", "分类"),
    ("specifications_json", "规格/参数"),
    ("features", "产品功能"),
    ("price", "价格"),
    ("moq", "MOQ"),
    ("packaging", "包装方式"),
    ("lead_time", "交期"),
    ("certifications", "认证"),
    ("payment_terms", "付款方式"),
    ("logistics_policy", "物流政策"),
    ("after_sales_policy", "售后政策"),
    ("oem_odm_terms", "OEM / ODM 条件"),
    ("faq", "常见问题"),
)


class ProductEditDialog(QDialog):
    def __init__(self, product=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑产品资料" if product else "新增产品资料")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.edits: dict[str, QLineEdit] = {}
        for key, label in _PRODUCT_FIELDS:
            edit = QLineEdit()
            edit.setObjectName(f"product_{key}")
            if product is not None:
                edit.setText(getattr(product, key) or "")
            self.edits[key] = edit
            form.addRow(label, edit)
        layout.addLayout(form)
        self.error_label = QLabel("")
        self.error_label.setObjectName("mutedText")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> dict:
        return {key: edit.text().strip() for key, edit in self.edits.items()}

    def _save(self) -> None:
        if not self.edits["name"].text().strip():
            self.error_label.setText("产品名称不能为空。")
            return
        self.accept()


class KnowledgePage(QWidget):
    status_message = Signal(str)

    def __init__(self, knowledge_service, parent=None):
        super().__init__(parent)
        self.knowledge_service = knowledge_service
        self.setObjectName("knowledgePage")
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)
        content = QWidget()
        content.setObjectName("pageContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)
        scroll.setWidget(content)

        title = QLabel("产品知识库")
        title.setObjectName("pageHeading")
        layout.addWidget(title)
        subtitle = QLabel(
            "导入产品目录、规格、报价和政策文件，使用本地全文检索；AI 分析仅检索与当前聊天相关的片段。"
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        notice = QLabel(
            "资料仅保存在本地。导入文件会复制到本地知识库目录，原始文件不会被修改或删除；不会上传整库资料。"
        )
        notice.setObjectName("mutedText")
        notice.setWordWrap(True)
        layout.addWidget(notice)

        search_card = QFrame()
        search_card.setObjectName("card")
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(16, 12, 16, 12)
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("knowledgeSearchEdit")
        self.search_edit.setPlaceholderText("搜索文件名、标题、分类或正文关键词")
        self.search_edit.returnPressed.connect(self.search)
        search_layout.addWidget(self.search_edit, 1)
        self.category_combo = QComboBox()
        self.category_combo.setObjectName("knowledgeCategoryCombo")
        self.category_combo.addItem("全部分类", None)
        self.category_combo.currentIndexChanged.connect(self.search)
        search_layout.addWidget(self.category_combo)
        self.search_button = QPushButton("搜索")
        self.search_button.clicked.connect(self.search)
        search_layout.addWidget(self.search_button)
        self.clear_button = QPushButton("重置")
        self.clear_button.clicked.connect(self.clear_search)
        search_layout.addWidget(self.clear_button)
        self.stats_label = QLabel("尚未导入资料")
        self.stats_label.setObjectName("mutedText")
        search_layout.addWidget(self.stats_label)
        layout.addWidget(search_card)

        document_card = QFrame()
        document_card.setObjectName("card")
        document_layout = QVBoxLayout(document_card)
        document_layout.setContentsMargins(18, 16, 18, 16)
        document_title = QLabel("文档资料")
        document_title.setObjectName("sectionHeading")
        document_layout.addWidget(document_title)
        import_row = QHBoxLayout()
        self.import_category_edit = QLineEdit()
        self.import_category_edit.setObjectName("importCategoryEdit")
        self.import_category_edit.setPlaceholderText("导入分类（可选，如 报价单/规格书）")
        self.import_category_edit.setMaximumWidth(260)
        import_row.addWidget(self.import_category_edit)
        self.document_product_combo = QComboBox()
        self.document_product_combo.setObjectName("documentProductCombo")
        self.document_product_combo.addItem("不关联产品", None)
        import_row.addWidget(self.document_product_combo)
        self.import_button = QPushButton("导入文件")
        self.import_button.setObjectName("primaryButton")
        self.import_button.clicked.connect(self._choose_import)
        import_row.addWidget(self.import_button)
        self.update_button = QPushButton("更新所选文件")
        self.update_button.clicked.connect(self._choose_update)
        import_row.addWidget(self.update_button)
        self.delete_button = QPushButton("删除所选文件")
        self.delete_button.clicked.connect(self._confirm_delete_document)
        import_row.addWidget(self.delete_button)
        import_row.addStretch(1)
        document_layout.addLayout(import_row)
        self.document_table = self._make_table(
            ("文件名", "标题", "分类", "产品", "类型", "导入时间")
        )
        self.document_table.itemSelectionChanged.connect(self.preview_selected_document)
        document_layout.addWidget(self.document_table)
        self.preview_edit = QPlainTextEdit()
        self.preview_edit.setObjectName("knowledgePreview")
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setPlaceholderText("选择文档后在此查看内容与资料来源")
        self.preview_edit.setMinimumHeight(180)
        document_layout.addWidget(self.preview_edit)
        self.status_label = QLabel("支持 PDF、DOCX、XLSX、CSV、TXT 和 Markdown。")
        self.status_label.setObjectName("mutedText")
        self.status_label.setWordWrap(True)
        document_layout.addWidget(self.status_label)
        layout.addWidget(document_card)

        product_card = QFrame()
        product_card.setObjectName("card")
        product_layout = QVBoxLayout(product_card)
        product_layout.setContentsMargins(18, 16, 18, 16)
        product_title = QLabel("结构化产品资料")
        product_title.setObjectName("sectionHeading")
        product_layout.addWidget(product_title)
        product_search_row = QHBoxLayout()
        self.product_search_edit = QLineEdit()
        self.product_search_edit.setObjectName("productSearchEdit")
        self.product_search_edit.setPlaceholderText("搜索产品名称、型号、分类、价格、MOQ 或认证")
        self.product_search_edit.returnPressed.connect(self.search_products)
        product_search_row.addWidget(self.product_search_edit, 1)
        self.product_search_button = QPushButton("搜索产品")
        self.product_search_button.clicked.connect(self.search_products)
        product_search_row.addWidget(self.product_search_button)
        self.add_product_button = QPushButton("新增产品")
        self.add_product_button.clicked.connect(self._add_product_dialog)
        product_search_row.addWidget(self.add_product_button)
        self.edit_product_button = QPushButton("编辑所选产品")
        self.edit_product_button.clicked.connect(self._edit_product_dialog)
        product_search_row.addWidget(self.edit_product_button)
        self.delete_product_button = QPushButton("删除所选产品")
        self.delete_product_button.clicked.connect(self._confirm_delete_product)
        product_search_row.addWidget(self.delete_product_button)
        product_layout.addLayout(product_search_row)
        self.product_table = self._make_table(
            ("名称", "型号", "分类", "价格", "MOQ", "交期")
        )
        product_layout.addWidget(self.product_table)
        layout.addWidget(product_card)
        layout.addStretch(1)

    @staticmethod
    def _make_table(headers: tuple[str, ...]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setMinimumHeight(150)
        return table

    def refresh(self) -> None:
        self._refresh_categories()
        self._refresh_product_combo()
        self.search()
        self.search_products()
        self._update_stats()

    def _refresh_categories(self) -> None:
        current = self.category_combo.currentData()
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItem("全部分类", None)
        for category in self.knowledge_service.categories():
            self.category_combo.addItem(category, category)
        index = self.category_combo.findData(current) if current else 0
        self.category_combo.setCurrentIndex(max(0, index))
        self.category_combo.blockSignals(False)

    def _refresh_product_combo(self) -> None:
        current = self.document_product_combo.currentData()
        self.document_product_combo.blockSignals(True)
        self.document_product_combo.clear()
        self.document_product_combo.addItem("不关联产品", None)
        for product in self.knowledge_service.search_products():
            label = product.name + (f" · {product.model}" if product.model else "")
            self.document_product_combo.addItem(label, product.id)
        index = self.document_product_combo.findData(current) if current else 0
        self.document_product_combo.setCurrentIndex(max(0, index))
        self.document_product_combo.blockSignals(False)

    def _update_stats(self) -> None:
        try:
            count = self.knowledge_service.repository.count_documents()
            products = len(self.knowledge_service.search_products())
        except Exception:
            logger.exception("统计知识库数量失败")
            return
        self.stats_label.setText(f"已导入 {count} 个文档 · {products} 个产品")

    def search(self) -> bool:
        query = self.search_edit.text().strip()
        category = self.category_combo.currentData()
        try:
            documents = self.knowledge_service.list_documents(
                search=query, category=category
            )
        except Exception as exc:
            logger.exception("搜索知识库失败")
            self._set_status(f"搜索失败：{exc}")
            return False
        self._fill_documents(documents)
        if query or category:
            self._set_status(f"找到 {len(documents)} 个匹配文档。")
        else:
            self._set_status("支持 PDF、DOCX、XLSX、CSV、TXT 和 Markdown。")
        return True

    def clear_search(self) -> None:
        self.search_edit.clear()
        self.category_combo.blockSignals(True)
        self.category_combo.setCurrentIndex(0)
        self.category_combo.blockSignals(False)
        self.search()

    def _fill_documents(self, documents) -> None:
        self.document_table.setRowCount(0)
        products = {
            product.id: product.name
            for product in self.knowledge_service.search_products()
        }
        for row, document in enumerate(documents):
            self.document_table.insertRow(row)
            name_item = QTableWidgetItem(document.file_name)
            name_item.setData(Qt.UserRole, document.id)
            self.document_table.setItem(row, 0, name_item)
            self.document_table.setItem(
                row, 1, QTableWidgetItem(document.title or "—")
            )
            self.document_table.setItem(row, 2, QTableWidgetItem(document.category))
            self.document_table.setItem(
                row,
                3,
                QTableWidgetItem(products.get(document.product_id, "—")),
            )
            self.document_table.setItem(
                row,
                4,
                QTableWidgetItem(
                    FILE_TYPE_LABELS.get(document.file_type, document.file_type)
                ),
            )
            self.document_table.setItem(
                row,
                5,
                QTableWidgetItem(
                    (document.imported_at or "—")[:16].replace("T", " ")
                ),
            )

    def import_file(
        self,
        path: str | Path,
        *,
        category: str = "",
        title: str = "",
        product_id: int | None = None,
    ) -> bool:
        try:
            document = self.knowledge_service.import_file(
                path,
                category=category,
                title=title,
                product_id=product_id,
            )
        except KnowledgeError as exc:
            self._set_status(str(exc))
            return False
        except Exception as exc:
            logger.exception("导入知识库文件失败")
            self._set_status(f"导入失败：{exc}")
            return False
        self.refresh()
        self._set_status(
            f"已导入《{document.title}》，并按 {FILE_TYPE_LABELS.get(document.file_type, document.file_type)}"
            " 解析索引；原始文件未修改。"
        )
        return True

    def preview_selected_document(self) -> bool:
        row = self.document_table.currentRow()
        if row < 0:
            return False
        item = self.document_table.item(row, 0)
        document_id = item.data(Qt.UserRole) if item else None
        if document_id is None:
            return False
        document = self.knowledge_service.preview(int(document_id))
        if document is None:
            self._set_status("所选文档已不存在，请刷新后重试。")
            return False
        self.preview_edit.setPlainText(
            f"来源文件：{document.file_name}\n"
            f"标题：{document.title or '—'}\n"
            f"分类：{document.category}\n"
            f"文件类型：{FILE_TYPE_LABELS.get(document.file_type, document.file_type)}\n"
            f"导入时间：{(document.imported_at or '—')[:19].replace('T', ' ')}\n"
            f"校验值：{document.checksum}\n\n"
            f"{document.content}"
        )
        return True

    def update_selected_document(self, path: str | Path) -> bool:
        row = self.document_table.currentRow()
        if row < 0:
            self._set_status("请先选择要更新的文档。")
            return False
        item = self.document_table.item(row, 0)
        document_id = item.data(Qt.UserRole) if item else None
        try:
            document = self.knowledge_service.update_file(int(document_id), path)
        except (KnowledgeError, TypeError, ValueError) as exc:
            self._set_status(str(exc))
            return False
        except Exception as exc:
            logger.exception("更新知识库文件失败")
            self._set_status(f"更新失败：{exc}")
            return False
        self.refresh()
        self._set_status(f"已更新《{document.title}》并重建本地检索索引。")
        return True

    def delete_selected_document(self) -> bool:
        row = self.document_table.currentRow()
        if row < 0:
            self._set_status("请先选择要删除的文档。")
            return False
        item = self.document_table.item(row, 0)
        document_id = item.data(Qt.UserRole) if item else None
        try:
            deleted = self.knowledge_service.delete(int(document_id))
        except Exception as exc:
            logger.exception("删除知识库文件失败")
            self._set_status(f"删除失败：{exc}")
            return False
        if not deleted:
            self._set_status("所选文档已不存在。")
            return False
        self.preview_edit.clear()
        self.refresh()
        self._set_status("已删除文档记录、检索索引和本地副本；原始文件未受影响。")
        return True

    def add_product(self, data: dict) -> bool:
        try:
            product = self.knowledge_service.add_product(data)
        except KnowledgeError as exc:
            self._set_status(str(exc))
            return False
        except Exception as exc:
            logger.exception("新增产品资料失败")
            self._set_status(f"新增失败：{exc}")
            return False
        self.refresh()
        self._set_status(f"已新增产品：{product.name}。")
        return True

    def search_products(self) -> bool:
        try:
            products = self.knowledge_service.search_products(
                self.product_search_edit.text()
            )
        except Exception as exc:
            logger.exception("搜索产品资料失败")
            self._set_status(f"产品搜索失败：{exc}")
            return False
        self._fill_products(products)
        return True

    def _fill_products(self, products) -> None:
        self.product_table.setRowCount(0)
        for row, product in enumerate(products):
            self.product_table.insertRow(row)
            name_item = QTableWidgetItem(product.name)
            name_item.setData(Qt.UserRole, product.id)
            self.product_table.setItem(row, 0, name_item)
            for column, value in enumerate(
                (product.model, product.category, product.price, product.moq, product.lead_time),
                start=1,
            ):
                self.product_table.setItem(row, column, QTableWidgetItem(value or "—"))

    def update_selected_product(self, data: dict) -> bool:
        product_id = self._selected_product_id()
        if product_id is None:
            self._set_status("请先选择要编辑的产品。")
            return False
        try:
            product = self.knowledge_service.update_product(product_id, data)
        except KnowledgeError as exc:
            self._set_status(str(exc))
            return False
        except Exception as exc:
            logger.exception("更新产品资料失败")
            self._set_status(f"更新失败：{exc}")
            return False
        self.refresh()
        self._set_status(f"已更新产品：{product.name}。")
        return True

    def delete_selected_product(self) -> bool:
        product_id = self._selected_product_id()
        if product_id is None:
            self._set_status("请先选择要删除的产品。")
            return False
        try:
            deleted = self.knowledge_service.delete_product(product_id)
        except Exception as exc:
            logger.exception("删除产品资料失败")
            self._set_status(f"删除失败：{exc}")
            return False
        if not deleted:
            self._set_status("所选产品已不存在。")
            return False
        self.refresh()
        self._set_status("已删除产品资料；关联文档保留但不再关联该产品。")
        return True

    def _selected_product_id(self):
        row = self.product_table.currentRow()
        if row < 0:
            return None
        item = self.product_table.item(row, 0)
        return None if item is None else item.data(Qt.UserRole)

    def _choose_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择知识库文件", "", _IMPORT_FILTER
        )
        if path:
            self.import_file(
                path,
                category=self.import_category_edit.text(),
                product_id=self.document_product_combo.currentData(),
            )

    def _choose_update(self) -> None:
        if self.document_table.currentRow() < 0:
            self._set_status("请先选择要更新的文档。")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择新版本文件", "", _IMPORT_FILTER
        )
        if path:
            self.update_selected_document(path)

    def _confirm_delete_document(self) -> None:
        if self.document_table.currentRow() < 0:
            self._set_status("请先选择要删除的文档。")
            return
        answer = QMessageBox.question(
            self,
            "删除知识库文档",
            "将删除本地知识库记录、检索索引和本地副本。原始导入文件不会被删除，确认继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.delete_selected_document()

    def _add_product_dialog(self) -> None:
        dialog = ProductEditDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.add_product(dialog.get_data())

    def _edit_product_dialog(self) -> None:
        product_id = self._selected_product_id()
        if product_id is None:
            self._set_status("请先选择要编辑的产品。")
            return
        product = self.knowledge_service.repository.get_product(product_id)
        if product is None:
            self._set_status("所选产品已不存在。")
            return
        dialog = ProductEditDialog(product, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.update_selected_product(dialog.get_data())

    def _confirm_delete_product(self) -> None:
        if self._selected_product_id() is None:
            self._set_status("请先选择要删除的产品。")
            return
        answer = QMessageBox.question(
            self,
            "删除产品资料",
            "确认删除所选产品资料？关联文档会保留，但不再关联该产品。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.delete_selected_product()

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_message.emit(message)
