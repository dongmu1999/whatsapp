"""知识库导入、解析、分类、全文检索与相关知识片段提取。"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
from pathlib import Path

from app.config import get_data_dir
from app.models.knowledge import (
    DEFAULT_CATEGORY,
    KNOWLEDGE_FILE_TYPES,
    MAX_IMPORT_BYTES,
    KnowledgeDocument,
    KnowledgeError,
    KnowledgeProduct,
    KnowledgeSnippet,
)
from app.models.message import CapturedMessage
from app.services.knowledge_parser import extract_document_text

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "the",
    "and",
    "for",
    "you",
    "your",
    "our",
    "with",
    "what",
    "which",
    "this",
    "that",
    "have",
    "has",
    "are",
    "can",
    "could",
    "would",
    "please",
    "about",
    "from",
    "need",
    "want",
    "price",
    "我们",
    "你们",
    "这个",
    "那个",
    "什么",
    "是否",
    "可以",
    "请问",
    "已经",
    "需要",
    "如果",
    "以及",
    "还有",
}


def _search_terms(text: str) -> list[str]:
    terms: list[str] = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9._-]{2,}", text):
        lowered = token.casefold()
        if lowered not in _STOPWORDS:
            terms.append(token)
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        if run in _STOPWORDS or len(run) < 3:
            continue
        # trigram 分词器只能命中 3 个字符以上的片段，这里生成 3 字窗口。
        terms.extend(run[index : index + 3] for index in range(len(run) - 2))
    unique: list[str] = []
    seen = set()
    for term in terms:
        key = term.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(term)
        if len(unique) >= 12:
            break
    return unique


def _match_query(text: str) -> str | None:
    terms = _search_terms(text)
    if not terms:
        return None
    return " OR ".join(f'"{term}"' for term in terms)


class KnowledgeService:
    def __init__(self, repository, storage_dir: str | Path | None = None):
        self.repository = repository
        self.storage_dir = (
            Path(storage_dir) if storage_dir is not None else get_data_dir() / "knowledge"
        )

    def import_file(
        self,
        path: str | Path,
        *,
        category: str = "",
        title: str = "",
        product_id: int | None = None,
    ) -> KnowledgeDocument:
        source, file_type, raw, checksum = self._prepare(path)
        if self.repository.find_by_checksum(checksum) is not None:
            raise KnowledgeError(f"相同内容的文件已导入：{source.name}")
        content = self._extract(source, file_type)
        target = self._copy_into_storage(raw, source.name, checksum)
        try:
            document_id = self.repository.insert_document(
                file_name=source.name,
                file_path=str(target),
                file_type=file_type,
                title=(title.strip() or source.stem),
                category=(category.strip() or DEFAULT_CATEGORY),
                content=content,
                checksum=checksum,
                product_id=product_id,
            )
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return self.repository.get_document(document_id)

    def update_file(self, document_id: int, path: str | Path) -> KnowledgeDocument:
        current = self.repository.get_document(document_id)
        if current is None:
            raise KnowledgeError("知识库文件记录不存在")
        source, file_type, raw, checksum = self._prepare(path)
        duplicate = self.repository.find_by_checksum(checksum)
        if duplicate is not None and duplicate.id != document_id:
            raise KnowledgeError(f"相同内容的文件已导入：{source.name}")
        content = self._extract(source, file_type)
        target = self._copy_into_storage(raw, source.name, checksum)
        try:
            self.repository.update_document(
                document_id,
                file_name=source.name,
                file_path=str(target),
                file_type=file_type,
                title=current.title or source.stem,
                category=current.category,
                content=content,
                checksum=checksum,
                product_id=current.product_id,
            )
        except Exception:
            target.unlink(missing_ok=True)
            raise
        old_path = Path(current.file_path)
        if old_path != target:
            self._unlink_storage_file(old_path)
        return self.repository.get_document(document_id)

    def delete(self, document_id: int) -> bool:
        document = self.repository.get_document(document_id)
        if document is None:
            return False
        if not self.repository.delete_document(document_id):
            return False
        self._unlink_storage_file(Path(document.file_path))
        return True

    def preview(self, document_id: int) -> KnowledgeDocument | None:
        return self.repository.get_document(document_id)

    def list_documents(
        self, *, search: str = "", category: str | None = None
    ) -> list[KnowledgeDocument]:
        query = search.strip()
        if not query:
            return self.repository.list_documents(category=category)
        match_query = _match_query(query)
        if match_query is not None:
            try:
                documents = self.repository.search_documents(
                    match_query, category=category
                )
            except sqlite3.Error:
                logger.exception("知识库全文检索失败，改用 LIKE 检索")
            else:
                if documents:
                    return documents
        return self.repository.like_documents(query, category=category)

    def search(
        self, query: str, *, category: str | None = None, limit: int = 20
    ) -> list[KnowledgeSnippet]:
        query = query.strip()
        if not query:
            return []
        match_query = _match_query(query)
        if match_query is not None:
            try:
                snippets = self.repository.search_snippets(
                    match_query, category=category, limit=limit
                )
            except sqlite3.Error:
                logger.exception("知识库片段检索失败，改用 LIKE 检索")
            else:
                if snippets:
                    return snippets
        return self.repository.like_snippets(query, category=category, limit=limit)

    def retrieve_for_messages(
        self, messages: list[CapturedMessage], *, limit: int = 5
    ) -> list[KnowledgeSnippet]:
        customer_text = [
            message.content
            for message in messages
            if message.sender_type == "customer"
        ][-10:]
        if not customer_text:
            customer_text = [message.content for message in messages][-6:]
        query = "\n".join(customer_text).strip()
        if len(query) < 2:
            return []
        snippets = self.search(query, limit=limit * 4)
        terms = _search_terms(query)
        if len(terms) >= 2 and snippets:
            filtered = [
                snippet
                for snippet in snippets
                if self._matched_term_count(snippet, terms) >= 2
            ]
            if filtered:
                snippets = filtered
        return snippets[:limit]

    def _matched_term_count(self, snippet: KnowledgeSnippet, terms: list[str]) -> int:
        document = self.repository.get_document(snippet.document_id)
        haystack = (
            f"{document.file_name}\n{document.title}\n{document.category}\n{document.content}"
            if document is not None
            else snippet.snippet
        ).casefold()
        return sum(1 for term in terms if term.casefold() in haystack)

    def categories(self) -> list[str]:
        return self.repository.categories()

    def search_products(self, query: str = "") -> list[KnowledgeProduct]:
        return self.repository.list_products(query)

    def add_product(self, data: dict) -> KnowledgeProduct:
        cleaned = self._clean_product(data, require_name=True)
        product_id = self.repository.add_product(cleaned)
        return self.repository.get_product(product_id)

    def update_product(self, product_id: int, data: dict) -> KnowledgeProduct:
        if self.repository.get_product(product_id) is None:
            raise KnowledgeError("产品记录不存在")
        cleaned = self._clean_product(data, require_name=False)
        self.repository.update_product(product_id, cleaned)
        return self.repository.get_product(product_id)

    def delete_product(self, product_id: int) -> bool:
        return self.repository.delete_product(product_id)

    @staticmethod
    def _clean_product(data: dict, *, require_name: bool) -> dict:
        cleaned = {}
        for key, value in data.items():
            if isinstance(value, str):
                value = value.strip() or None
            cleaned[key] = value
        name = cleaned.get("name")
        if require_name and not name:
            raise KnowledgeError("产品名称不能为空")
        if "specifications_json" in cleaned and isinstance(
            cleaned["specifications_json"], (dict, list)
        ):
            cleaned["specifications_json"] = json.dumps(
                cleaned["specifications_json"], ensure_ascii=False
            )
        return cleaned

    def _prepare(self, path: str | Path):
        source = Path(path).expanduser()
        if not source.is_file():
            raise KnowledgeError("文件不存在，请重新选择")
        suffix = source.suffix.casefold()
        if suffix not in KNOWLEDGE_FILE_TYPES:
            raise KnowledgeError(
                f"不支持的文件类型：{suffix or '无扩展名'}；"
                "仅支持 PDF、DOCX、XLSX、CSV、TXT、Markdown"
            )
        if source.stat().st_size > MAX_IMPORT_BYTES:
            raise KnowledgeError("文件超过 20 MB，无法导入")
        raw = source.read_bytes()
        checksum = hashlib.sha256(raw).hexdigest()
        return source, KNOWLEDGE_FILE_TYPES[suffix], raw, checksum

    @staticmethod
    def _extract(source: Path, file_type: str) -> str:
        try:
            content = extract_document_text(source, file_type)
        except KnowledgeError:
            raise
        except Exception as exc:
            raise KnowledgeError(f"文件解析失败：{exc}") from exc
        if not content.strip():
            raise KnowledgeError("文件未提取到可用文本")
        return content

    def _copy_into_storage(self, raw: bytes, file_name: str, checksum: str) -> Path:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "_", file_name)
        target = self.storage_dir / f"{checksum[:10]}_{safe_name}"
        try:
            target.write_bytes(raw)
        except OSError as exc:
            raise KnowledgeError(f"复制文件到本地知识库失败：{exc}") from exc
        return target

    def _unlink_storage_file(self, path: Path) -> None:
        try:
            if path.resolve().parent == self.storage_dir.resolve():
                path.unlink(missing_ok=True)
        except OSError:
            logger.exception("删除知识库副本失败：%s", path.name)
