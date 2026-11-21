"""产品知识库的 SQLite 持久化与全文检索。"""

from __future__ import annotations

from app.database.connection import Database
from app.models.knowledge import KnowledgeDocument, KnowledgeProduct, KnowledgeSnippet

_DOCUMENT_FIELDS = (
    "id",
    "product_id",
    "file_name",
    "file_path",
    "file_type",
    "title",
    "category",
    "content",
    "checksum",
    "status",
    "error_message",
    "imported_at",
    "updated_at",
)
_DOCUMENT_COLUMNS = ", ".join(_DOCUMENT_FIELDS)

_PRODUCT_FIELDS = (
    "name",
    "model",
    "category",
    "specifications_json",
    "features",
    "price",
    "moq",
    "packaging",
    "lead_time",
    "certifications",
    "payment_terms",
    "logistics_policy",
    "after_sales_policy",
    "oem_odm_terms",
    "faq",
)


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class KnowledgeRepository:
    def __init__(self, database: Database):
        self.database = database

    def insert_document(
        self,
        *,
        file_name: str,
        file_path: str,
        file_type: str,
        title: str,
        category: str,
        content: str,
        checksum: str,
        product_id: int | None = None,
    ) -> int:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO knowledge_documents(
                    product_id, file_name, file_path, file_type, title, category,
                    content, checksum, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'indexed')
                """,
                (
                    product_id,
                    file_name,
                    file_path,
                    file_type,
                    title,
                    category,
                    content,
                    checksum,
                ),
            )
            return int(cursor.lastrowid)

    def update_document(
        self,
        document_id: int,
        *,
        file_name: str,
        file_path: str,
        file_type: str,
        title: str,
        category: str,
        content: str,
        checksum: str,
        product_id: int | None,
    ) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE knowledge_documents SET
                    product_id = ?, file_name = ?, file_path = ?, file_type = ?,
                    title = ?, category = ?, content = ?, checksum = ?,
                    status = 'indexed', error_message = NULL,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                (
                    product_id,
                    file_name,
                    file_path,
                    file_type,
                    title,
                    category,
                    content,
                    checksum,
                    document_id,
                ),
            )

    def delete_document(self, document_id: int) -> bool:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM knowledge_documents WHERE id = ?", (document_id,)
            )
            return cursor.rowcount > 0

    def get_document(self, document_id: int) -> KnowledgeDocument | None:
        row = self.database.connection.execute(
            f"SELECT {_DOCUMENT_COLUMNS} FROM knowledge_documents WHERE id = ?",
            (document_id,),
        ).fetchone()
        return None if row is None else KnowledgeDocument.from_row(row)

    def find_by_checksum(self, checksum: str) -> KnowledgeDocument | None:
        row = self.database.connection.execute(
            f"SELECT {_DOCUMENT_COLUMNS} FROM knowledge_documents WHERE checksum = ?",
            (checksum,),
        ).fetchone()
        return None if row is None else KnowledgeDocument.from_row(row)

    def list_documents(self, *, category: str | None = None) -> list[KnowledgeDocument]:
        sql = f"SELECT {_DOCUMENT_COLUMNS} FROM knowledge_documents"
        params: list = []
        if category:
            sql += " WHERE category = ?"
            params.append(category)
        sql += " ORDER BY imported_at DESC, id DESC"
        rows = self.database.connection.execute(sql, params).fetchall()
        return [KnowledgeDocument.from_row(row) for row in rows]

    def search_documents(
        self, match_query: str, *, category: str | None = None, limit: int = 50
    ) -> list[KnowledgeDocument]:
        sql = f"""
            SELECT {", ".join(f"d.{name}" for name in _DOCUMENT_FIELDS)}
            FROM knowledge_search
            JOIN knowledge_documents AS d ON d.id = knowledge_search.rowid
            WHERE knowledge_search MATCH ?
        """
        params: list = [match_query]
        if category:
            sql += " AND d.category = ?"
            params.append(category)
        sql += " ORDER BY bm25(knowledge_search) LIMIT ?"
        params.append(limit)
        rows = self.database.connection.execute(sql, params).fetchall()
        return [KnowledgeDocument.from_row(row) for row in rows]

    def search_snippets(
        self, match_query: str, *, category: str | None = None, limit: int = 20
    ) -> list[KnowledgeSnippet]:
        sql = """
            SELECT d.id, d.file_name, coalesce(d.title, '') AS title,
                   coalesce(d.category, '') AS category,
                   snippet(knowledge_search, 3, '【', '】', '…', 48) AS matched
            FROM knowledge_search
            JOIN knowledge_documents AS d ON d.id = knowledge_search.rowid
            WHERE knowledge_search MATCH ?
        """
        params: list = [match_query]
        if category:
            sql += " AND d.category = ?"
            params.append(category)
        sql += " ORDER BY bm25(knowledge_search) LIMIT ?"
        params.append(limit)
        rows = self.database.connection.execute(sql, params).fetchall()
        return [
            KnowledgeSnippet(
                document_id=int(row["id"]),
                file_name=row["file_name"],
                title=row["title"],
                category=row["category"],
                snippet=row["matched"] or "",
            )
            for row in rows
        ]

    def like_documents(
        self, term: str, *, category: str | None = None, limit: int = 50
    ) -> list[KnowledgeDocument]:
        pattern = f"%{_escape_like(term)}%"
        sql = f"""
            SELECT {_DOCUMENT_COLUMNS} FROM knowledge_documents
            WHERE (
                file_name LIKE ? ESCAPE '\\' OR title LIKE ? ESCAPE '\\'
                OR category LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\'
            )
        """
        params: list = [pattern, pattern, pattern, pattern]
        if category:
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY imported_at DESC, id DESC LIMIT ?"
        params.append(limit)
        rows = self.database.connection.execute(sql, params).fetchall()
        return [KnowledgeDocument.from_row(row) for row in rows]

    def like_snippets(
        self, term: str, *, category: str | None = None, limit: int = 20
    ) -> list[KnowledgeSnippet]:
        documents = self.like_documents(term, category=category, limit=limit)
        lowered = term.casefold()
        snippets = []
        for document in documents:
            content = document.content
            index = content.casefold().find(lowered)
            if index < 0:
                matched = content[:160]
            else:
                start = max(0, index - 60)
                matched = content[start : start + 160]
            snippets.append(
                KnowledgeSnippet(
                    document_id=document.id,
                    file_name=document.file_name,
                    title=document.title,
                    category=document.category,
                    snippet=matched,
                )
            )
        return snippets

    def categories(self) -> list[str]:
        rows = self.database.connection.execute(
            """
            SELECT DISTINCT category FROM knowledge_documents
            WHERE category IS NOT NULL AND category != ''
            ORDER BY category
            """
        ).fetchall()
        return [row["category"] for row in rows]

    def add_product(self, data: dict) -> int:
        values = [data.get(field) for field in _PRODUCT_FIELDS]
        columns = ", ".join(_PRODUCT_FIELDS)
        placeholders = ", ".join("?" for _ in _PRODUCT_FIELDS)
        with self.database.transaction() as connection:
            cursor = connection.execute(
                f"INSERT INTO products({columns}) VALUES ({placeholders})", values
            )
            return int(cursor.lastrowid)

    def update_product(self, product_id: int, data: dict) -> bool:
        current = self.get_product(product_id)
        if current is None:
            return False
        merged = {field: getattr(current, field) for field in _PRODUCT_FIELDS}
        merged.update({key: value for key, value in data.items() if key in merged})
        assignments = ", ".join(f"{field} = ?" for field in _PRODUCT_FIELDS)
        values = [merged.get(field) for field in _PRODUCT_FIELDS]
        with self.database.transaction() as connection:
            connection.execute(
                f"""
                UPDATE products SET {assignments},
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                (*values, product_id),
            )
        return True

    def delete_product(self, product_id: int) -> bool:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM products WHERE id = ?", (product_id,)
            )
            return cursor.rowcount > 0

    def get_product(self, product_id: int) -> KnowledgeProduct | None:
        row = self.database.connection.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        return None if row is None else KnowledgeProduct.from_row(row)

    def list_products(self, search: str = "") -> list[KnowledgeProduct]:
        sql = "SELECT * FROM products"
        params: tuple = ()
        if search.strip():
            pattern = f"%{_escape_like(search.strip())}%"
            sql += """
                WHERE name LIKE ? ESCAPE '\\' OR model LIKE ? ESCAPE '\\'
                   OR category LIKE ? ESCAPE '\\' OR features LIKE ? ESCAPE '\\'
                   OR price LIKE ? ESCAPE '\\' OR moq LIKE ? ESCAPE '\\'
                   OR certifications LIKE ? ESCAPE '\\'
            """
            params = (pattern,) * 7
        sql += " ORDER BY updated_at DESC, id DESC"
        rows = self.database.connection.execute(sql, params).fetchall()
        return [KnowledgeProduct.from_row(row) for row in rows]

    def count_documents(self) -> int:
        return int(
            self.database.connection.execute(
                "SELECT COUNT(*) FROM knowledge_documents"
            ).fetchone()[0]
        )
