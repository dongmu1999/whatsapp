"""PDF、Word、Excel、CSV、文本与 Markdown 的本地文本提取。"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from app.models.knowledge import MAX_CONTENT_CHARS, KnowledgeError

_MAX_SHEET_ROWS = 3000
_ENCODINGS = ("utf-8-sig", "gb18030")


def _decode(raw: bytes) -> str:
    for encoding in _ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _read_text(path: Path) -> str:
    return _decode(path.read_bytes())


def _read_csv(path: Path) -> str:
    text = _decode(path.read_bytes())
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = []
    for row in csv.reader(io.StringIO(text), dialect):
        cells = [cell.strip() for cell in row if cell and cell.strip()]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _read_xlsx(path: Path) -> str:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - 依赖缺失时的明确提示
        raise KnowledgeError("缺少 Excel 解析依赖 openpyxl，请重新安装运行依赖") from exc
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise KnowledgeError(f"Excel 文件无法读取：{exc}") from exc
    lines: list[str] = []
    try:
        for sheet in workbook.worksheets:
            lines.append(f"# {sheet.title}")
            for index, row in enumerate(sheet.iter_rows(values_only=True)):
                if index >= _MAX_SHEET_ROWS:
                    lines.append("…（工作表内容过长，已截断）")
                    break
                cells = [str(value).strip() for value in row if value not in (None, "")]
                if cells:
                    lines.append(" | ".join(cells))
                if sum(len(line) for line in lines) >= MAX_CONTENT_CHARS:
                    return "\n".join(lines)[:MAX_CONTENT_CHARS]
    finally:
        workbook.close()
    return "\n".join(lines)


def _read_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover - 依赖缺失时的明确提示
        raise KnowledgeError("缺少 Word 解析依赖 python-docx，请重新安装运行依赖") from exc
    try:
        document = Document(path)
    except Exception as exc:
        raise KnowledgeError(f"Word 文件无法读取：{exc}") from exc
    lines = [paragraph.text.strip() for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                lines.append(" | ".join(cells))
    return "\n".join(line for line in lines if line)


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - 依赖缺失时的明确提示
        raise KnowledgeError("缺少 PDF 解析依赖 pypdf，请重新安装运行依赖") from exc
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise KnowledgeError("PDF 已加密，无法读取文本")
        pages = [page.extract_text() or "" for page in reader.pages]
    except KnowledgeError:
        raise
    except Exception as exc:
        raise KnowledgeError(f"PDF 文件无法读取：{exc}") from exc
    text = "\n".join(page.strip() for page in pages if page.strip())
    if not text:
        raise KnowledgeError(
            "PDF 未提取到文本，可能是扫描件；请先使用 OCR 或提供文本版文件"
        )
    return text


def extract_document_text(path: Path, file_type: str) -> str:
    """按文件类型提取可检索文本，并限制总长度。"""
    if file_type == "pdf":
        text = _read_pdf(path)
    elif file_type == "docx":
        text = _read_docx(path)
    elif file_type == "xlsx":
        text = _read_xlsx(path)
    elif file_type == "csv":
        text = _read_csv(path)
    else:
        text = _read_text(path)
    text = text.strip()
    if len(text) > MAX_CONTENT_CHARS:
        text = text[:MAX_CONTENT_CHARS] + "\n…（内容过长，已截断）"
    return text
