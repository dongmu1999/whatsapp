from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from docx import Document
from openpyxl import Workbook
from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)

from app.database.connection import Database
from app.database.repositories.knowledge_repository import KnowledgeRepository
from app.database.schema import INITIAL_SCHEMA
from app.models.knowledge import KnowledgeError, KnowledgeSnippet
from app.models.message import CapturedMessage
from app.services.deepseek_service import Completion
from app.services.knowledge_service import KnowledgeService
from app.services.sales_advisor_service import SalesAdvisorService
from test_analysis import FakeClient, payload, stats


@pytest.fixture()
def service(database, tmp_path):
    return KnowledgeService(KnowledgeRepository(database), storage_dir=tmp_path / "knowledge")


def _write(path: Path, text: str, encoding: str = "utf-8") -> Path:
    path.write_text(text, encoding=encoding)
    return path


def _write_docx(path: Path) -> Path:
    document = Document()
    document.add_paragraph("防水蓝牙音箱 BT-500")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "MOQ"
    table.cell(0, 1).text = "500 pcs"
    document.save(path)
    return path


def _write_xlsx(path: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["产品", "型号", "价格"])
    sheet.append(["办公椅", "CH-200", "USD 35"])
    workbook.save(path)
    return path


def _write_pdf(path: Path, text: str = "MOQ 500 pcs lead time 25 days") -> Path:
    writer = PdfWriter()
    page = writer.add_blank_page(300, 300)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 20 150 Td ({text}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def test_import_txt_copies_source_indexes_and_tracks_metadata(service, tmp_path):
    source = _write(
        tmp_path / "quote.txt", "MOQ 500 pcs\n交期 25 天\n价格 USD 12"
    )

    document = service.import_file(
        source, category="报价单", title="蓝牙音箱报价"
    )

    assert document.status == "indexed"
    assert document.file_type == "txt"
    assert document.file_name == "quote.txt"
    assert document.category == "报价单"
    assert document.title == "蓝牙音箱报价"
    assert document.checksum
    assert Path(document.file_path).exists()
    assert Path(document.file_path) != source
    assert "MOQ 500 pcs" in service.preview(document.id).content
    assert [item.id for item in service.list_documents()] == [document.id]
    assert [item.id for item in service.list_documents(search="交期")] == [document.id]
    assert service.categories() == ["报价单"]

    snippets = service.search("MOQ 500")
    assert snippets
    assert snippets[0].file_name == "quote.txt"
    assert "MOQ" in snippets[0].snippet
    assert "500 pcs" in snippets[0].snippet


def test_import_rejects_duplicates_unsupported_missing_and_empty_files(service, tmp_path):
    source = _write(tmp_path / "quote.txt", "MOQ 500 pcs")
    service.import_file(source)

    with pytest.raises(KnowledgeError, match="相同内容"):
        service.import_file(source)
    with pytest.raises(KnowledgeError, match="不支持"):
        service.import_file(_write(tmp_path / "virus.exe", "binary"))
    with pytest.raises(KnowledgeError, match="不存在"):
        service.import_file(tmp_path / "missing.pdf")
    with pytest.raises(KnowledgeError, match="未提取到"):
        service.import_file(_write(tmp_path / "empty.txt", "   \n  "))


def test_pdf_word_excel_and_csv_files_are_parsed(service, tmp_path):
    pdf = service.import_file(_write_pdf(tmp_path / "catalog.pdf"), category="产品")
    docx = service.import_file(_write_docx(tmp_path / "spec.docx"), category="产品")
    xlsx = service.import_file(_write_xlsx(tmp_path / "price.xlsx"), category="报价单")
    csv_path = _write(
        tmp_path / "stock.csv", "产品,型号,库存\n蓝牙音箱,BT-500,120\n", encoding="gb18030"
    )
    csv_document = service.import_file(csv_path, category="库存")

    assert "MOQ 500 pcs" in pdf.content
    assert "防水蓝牙音箱 BT-500" in docx.content
    assert "500 pcs" in docx.content
    assert "办公椅" in xlsx.content and "CH-200" in xlsx.content
    assert "蓝牙音箱" in csv_document.content and "120" in csv_document.content

    assert {item.file_type for item in service.list_documents()} == {
        "pdf",
        "docx",
        "xlsx",
        "csv",
    }
    assert service.search("BT-500")
    assert service.search("办公椅")


def test_blank_pdf_reports_scanned_document(service, tmp_path):
    with pytest.raises(KnowledgeError, match="未提取到文本"):
        service.import_file(_write_pdf(tmp_path / "blank.pdf", ""))


def test_update_file_replaces_content_checksum_and_index(service, tmp_path):
    first = service.import_file(
        _write(tmp_path / "v1.txt", "型号 A100 价格 USD 10"), category="报价单"
    )
    old_path = Path(first.file_path)

    updated = service.update_file(
        first.id, _write(tmp_path / "v2.txt", "型号 B200 交期 30 天")
    )

    assert updated.id == first.id
    assert updated.file_name == "v2.txt"
    assert updated.checksum != first.checksum
    assert "B200" in service.preview(first.id).content
    assert not old_path.exists()
    assert service.search("A100") == []
    assert service.search("B200")
    assert service.search("B200")[0].document_id == first.id


def test_delete_removes_record_index_and_copied_file(service, tmp_path):
    document = service.import_file(
        _write(tmp_path / "quote.txt", "MOQ 500 pcs"), category="报价单"
    )
    copied = Path(document.file_path)
    assert copied.exists()

    assert service.delete(document.id)

    assert service.list_documents() == []
    assert service.search("MOQ 500") == []
    assert not copied.exists()
    assert not service.delete(document.id)


def test_retrieval_returns_only_snippets_relevant_to_current_messages(service, tmp_path):
    service.import_file(
        _write(tmp_path / "speaker.txt", "防水蓝牙音箱 MOQ 500 pcs，交期 25 天"),
        category="产品",
    )
    service.import_file(
        _write(tmp_path / "chair.txt", "人体工学办公椅 MOQ 100 pcs，交期 30 天"),
        category="产品",
    )

    snippets = service.retrieve_for_messages(
        [
            CapturedMessage(
                "Do you have a waterproof Bluetooth speaker? What is the MOQ?",
                sender_type="customer",
            )
        ]
    )

    assert [item.file_name for item in snippets] == ["speaker.txt"]


def test_category_filter_limits_search_results(service, tmp_path):
    service.import_file(_write(tmp_path / "quote.txt", "MOQ 500 pcs"), category="报价单")
    service.import_file(_write(tmp_path / "spec.txt", "MOQ 500 pcs on carton"), category="规格")

    assert [item.category for item in service.search("MOQ", category="报价单")] == ["报价单"]
    assert service.search("MOQ", category="售后") == []
    assert len(service.search("MOQ")) == 2


def test_product_records_support_create_update_search_and_delete(service):
    product = service.add_product(
        {
            "name": "防水蓝牙音箱",
            "model": "BT-500",
            "category": "音箱",
            "price": "USD 12",
            "moq": "500 pcs",
            "lead_time": "25 天",
            "certifications": "CE, RoHS",
        }
    )

    assert [item.id for item in service.search_products("BT-500")] == [product.id]
    assert [item.id for item in service.search_products("蓝牙")] == [product.id]

    updated = service.update_product(product.id, {"price": "USD 11", "moq": "300 pcs"})
    assert updated.price == "USD 11"
    assert updated.moq == "300 pcs"
    assert updated.name == "防水蓝牙音箱"

    assert service.delete_product(product.id)
    assert service.search_products("BT-500") == []


def test_existing_phase_five_database_upgrades_and_rebuilds_index(tmp_path):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.executescript(INITIAL_SCHEMA)
    connection.execute(
        "INSERT INTO database_migrations(version, name) VALUES (1, 'initial_schema')"
    )
    connection.execute(
        """
        INSERT INTO knowledge_documents(
            file_name, file_path, file_type, title, category, content, checksum
        ) VALUES ('old.txt', '/tmp/old.txt', 'txt', '旧报价', '报价单',
                  '旧资料 MOQ 500 pcs 交期 25 天', 'legacy-checksum')
        """
    )
    connection.commit()
    connection.close()

    database = Database(path)
    try:
        assert database.initialize() == [2]
        service = KnowledgeService(
            KnowledgeRepository(database), storage_dir=tmp_path / "knowledge"
        )
        assert service.search("MOQ")[0].file_name == "old.txt"
        assert service.list_documents(search="交期")[0].title == "旧报价"
    finally:
        database.close()


def test_advisor_injects_only_provided_knowledge_and_parses_references():
    data = payload()
    data["knowledge_references"] = [
        {"source": "quote.txt", "fact": "MOQ 500 pcs，交期 25 天"}
    ]
    client = FakeClient([Completion(json.dumps(data), stats())])
    snippet = KnowledgeSnippet(
        document_id=1,
        file_name="quote.txt",
        title="蓝牙音箱报价",
        category="报价单",
        snippet="MOQ 500 pcs，交期 25 天",
    )

    result = SalesAdvisorService(client).analyze(
        1,
        2,
        [CapturedMessage("What is your MOQ?", sender_type="customer")],
        knowledge_snippets=[snippet],
    )

    prompt = json.dumps(client.calls[0]["messages"], ensure_ascii=False)
    assert "知识库参考" in prompt
    assert "quote.txt" in prompt
    assert "MOQ 500 pcs，交期 25 天" in prompt
    assert "客户提供" in prompt
    assert "AI 推测" in prompt
    assert result.analysis.knowledge_references[0].source == "quote.txt"

    without_knowledge = FakeClient([Completion(json.dumps(payload()), stats())])
    result = SalesAdvisorService(without_knowledge).analyze(
        1, None, [CapturedMessage("What is your MOQ?")]
    )
    prompt = json.dumps(without_knowledge.calls[0]["messages"], ensure_ascii=False)
    assert "未提供知识库参考" in prompt
    assert result.analysis.knowledge_references == []
