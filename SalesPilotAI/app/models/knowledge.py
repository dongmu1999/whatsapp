"""产品知识库数据模型与文件类型约束。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

KNOWLEDGE_FILE_TYPES = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".xlsx": "xlsx",
    ".csv": "csv",
    ".txt": "txt",
    ".md": "md",
    ".markdown": "md",
}
FILE_TYPE_LABELS = {
    "pdf": "PDF",
    "docx": "Word",
    "xlsx": "Excel",
    "csv": "CSV",
    "txt": "文本",
    "md": "Markdown",
}
MAX_IMPORT_BYTES = 20 * 1024 * 1024
MAX_CONTENT_CHARS = 200_000
DEFAULT_CATEGORY = "未分类"


class KnowledgeError(ValueError):
    """知识库导入、解析或维护失败。"""


@dataclass(frozen=True)
class KnowledgeDocument:
    id: int
    file_name: str
    file_path: str
    file_type: str
    title: str
    category: str
    content: str
    checksum: str
    status: str
    error_message: str | None = None
    product_id: int | None = None
    imported_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "KnowledgeDocument":
        return cls(
            id=int(row["id"]),
            file_name=row["file_name"],
            file_path=row["file_path"],
            file_type=row["file_type"],
            title=row["title"] or "",
            category=row["category"] or DEFAULT_CATEGORY,
            content=row["content"] or "",
            checksum=row["checksum"],
            status=row["status"],
            error_message=row["error_message"],
            product_id=row["product_id"],
            imported_at=row["imported_at"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True)
class KnowledgeProduct:
    id: int
    name: str
    model: str | None = None
    category: str | None = None
    specifications_json: str | None = None
    features: str | None = None
    price: str | None = None
    moq: str | None = None
    packaging: str | None = None
    lead_time: str | None = None
    certifications: str | None = None
    payment_terms: str | None = None
    logistics_policy: str | None = None
    after_sales_policy: str | None = None
    oem_odm_terms: str | None = None
    faq: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "KnowledgeProduct":
        return cls(
            id=int(row["id"]),
            name=row["name"],
            model=row["model"],
            category=row["category"],
            specifications_json=row["specifications_json"],
            features=row["features"],
            price=row["price"],
            moq=row["moq"],
            packaging=row["packaging"],
            lead_time=row["lead_time"],
            certifications=row["certifications"],
            payment_terms=row["payment_terms"],
            logistics_policy=row["logistics_policy"],
            after_sales_policy=row["after_sales_policy"],
            oem_odm_terms=row["oem_odm_terms"],
            faq=row["faq"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@dataclass(frozen=True)
class KnowledgeSnippet:
    document_id: int
    file_name: str
    title: str
    category: str
    snippet: str
