from __future__ import annotations

from pathlib import Path

from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QLabel, QMessageBox

from app.database.repositories.knowledge_repository import KnowledgeRepository
from app.models.analysis import SalesAnalysis
from app.models.knowledge import KnowledgeSnippet
from app.services.knowledge_service import KnowledgeService
from app.ui.analysis_result import AnalysisResultWidget
from app.ui.knowledge_page import KnowledgePage
from app.ui.main_window import MainWindow
from test_ai_ui import FakeAdvisor, _make_analysis_page, _wait_for_signal
from test_analysis import payload


def _service(database, tmp_path) -> KnowledgeService:
    return KnowledgeService(
        KnowledgeRepository(database), storage_dir=tmp_path / "knowledge"
    )


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_knowledge_page_imports_previews_searches_and_deletes(
    application, database, tmp_path
):
    page = KnowledgePage(_service(database, tmp_path))
    source = _write(tmp_path / "quote.txt", "MOQ 500 pcs\n交期 25 天")

    assert page.import_file(source, category="报价单")
    assert page.document_table.rowCount() == 1
    assert page.category_combo.findData("报价单") >= 0
    assert "1" in page.stats_label.text()

    page.document_table.selectRow(0)
    assert page.preview_selected_document()
    assert "MOQ 500 pcs" in page.preview_edit.toPlainText()
    assert "quote.txt" in page.preview_edit.toPlainText()

    page.search_edit.setText("交期")
    assert page.search()
    assert page.document_table.rowCount() == 1
    page.search_edit.setText("不存在的关键词")
    assert page.search()
    assert page.document_table.rowCount() == 0

    page.search_edit.clear()
    page.category_combo.setCurrentIndex(page.category_combo.findData("报价单"))
    assert page.search()
    assert page.document_table.rowCount() == 1

    page.document_table.selectRow(0)
    assert page.delete_selected_document()
    assert page.document_table.rowCount() == 0
    page.close()


def test_knowledge_page_manages_structured_products(application, database, tmp_path):
    page = KnowledgePage(_service(database, tmp_path))

    assert page.add_product(
        {
            "name": "防水蓝牙音箱",
            "model": "BT-500",
            "category": "音箱",
            "price": "USD 12",
            "moq": "500 pcs",
            "lead_time": "25 天",
        }
    )
    assert page.product_table.rowCount() == 1

    page.product_search_edit.setText("BT-500")
    assert page.search_products()
    assert page.product_table.rowCount() == 1
    page.product_table.selectRow(0)
    assert page.delete_selected_product()
    assert page.product_table.rowCount() == 0
    page.close()


def test_analysis_confirmation_reports_and_passes_relevant_knowledge(
    application, database, monkeypatch
):
    snippet = KnowledgeSnippet(
        document_id=3,
        file_name="quote.txt",
        title="蓝牙音箱报价",
        category="报价单",
        snippet="MOQ 500 pcs，交期 25 天",
    )

    class StubKnowledge:
        def __init__(self):
            self.calls = []

        def retrieve_for_messages(self, messages, limit=5):
            self.calls.append((messages, limit))
            return [snippet]

    knowledge = StubKnowledge()
    advisor = FakeAdvisor()
    page, _ = _make_analysis_page(database, advisor, knowledge_service=knowledge)
    confirmations = []

    def confirm(*args, **kwargs):
        confirmations.append(args[2])
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", confirm)
    completed = QSignalSpy(page.analysis_completed)

    assert page.start_analysis()
    _wait_for_signal(application, completed)
    application.processEvents()

    assert knowledge.calls
    assert "知识库相关片段：1 条" in confirmations[0]
    passed = advisor.calls[0][3]["knowledge_snippets"]
    assert [item.file_name for item in passed] == ["quote.txt"]
    page.close()


def test_analysis_result_lists_knowledge_references(application):
    data = payload()
    data["knowledge_references"] = [
        {"source": "quote.txt", "fact": "MOQ 500 pcs，交期 25 天"}
    ]
    widget = AnalysisResultWidget()

    widget.set_analysis(SalesAnalysis.model_validate(data))

    assert "quote.txt" in widget.knowledge_label.text()
    assert "MOQ 500 pcs" in widget.knowledge_label.text()
    widget.close()


def test_main_window_integrates_phase_six(application, database, tmp_path, monkeypatch):
    monkeypatch.setenv("SALESPILOT_DATA_DIR", str(tmp_path))
    window = MainWindow(database)
    try:
        assert isinstance(window.knowledge_page, KnowledgePage)
        assert window.pages.widget(4) is window.knowledge_page
        assert window.chat_analysis_page.knowledge_service is not None
        version = window.findChild(QLabel, "sidebarVersion")
        assert "阶段 6" in version.text()
    finally:
        window.close()
