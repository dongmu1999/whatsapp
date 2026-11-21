"""客户记忆的本地持久化，所有查询均按 customer_id 隔离。"""

from __future__ import annotations

from app.database.connection import Database
from app.models.memory import CustomerMemory, MemoryNotFoundError
from app.models.message import utc_now_text

_ROW_COLUMNS = """
    id, customer_id, category, content, source, status, confirmed_at,
    created_at, updated_at
"""


class MemoryRepository:
    def __init__(self, database: Database):
        self.database = database

    def insert(
        self,
        customer_id: int,
        category: str,
        content: str,
        *,
        source: str,
        status: str,
        confirmed_at: str | None = None,
    ) -> int:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO customer_memories(
                    customer_id, category, content, source, status, confirmed_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (customer_id, category, content, source, status, confirmed_at),
            )
            return int(cursor.lastrowid)

    def list(
        self, customer_id: int, *, status: str | None = None, search: str = ""
    ) -> list[CustomerMemory]:
        keyword = str(search or "").strip()
        rows = self.database.connection.execute(
            f"""
            SELECT {_ROW_COLUMNS}
            FROM customer_memories
            WHERE customer_id = ?
              AND (? IS NULL OR status = ?)
              AND (? = '' OR content LIKE ?)
            ORDER BY created_at DESC, id DESC
            """,
            (customer_id, status, status, keyword, f"%{keyword}%"),
        ).fetchall()
        return [CustomerMemory.from_row(row) for row in rows]

    def get(self, customer_id: int, memory_id: int) -> CustomerMemory:
        row = self.database.connection.execute(
            f"""
            SELECT {_ROW_COLUMNS}
            FROM customer_memories
            WHERE customer_id = ? AND id = ?
            """,
            (customer_id, memory_id),
        ).fetchone()
        if row is None:
            raise MemoryNotFoundError("记忆不存在，或不属于当前客户")
        return CustomerMemory.from_row(row)

    def update(
        self,
        customer_id: int,
        memory_id: int,
        *,
        category: str,
        content: str,
    ) -> CustomerMemory:
        self.get(customer_id, memory_id)
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE customer_memories
                SET category = ?, content = ?, updated_at = ?
                WHERE customer_id = ? AND id = ?
                """,
                (category, content, utc_now_text(), customer_id, memory_id),
            )
        return self.get(customer_id, memory_id)

    def set_status(
        self, customer_id: int, memory_id: int, status: str
    ) -> CustomerMemory:
        self.get(customer_id, memory_id)
        confirmed_at = utc_now_text() if status == "confirmed" else None
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE customer_memories
                SET status = ?, confirmed_at = ?, updated_at = ?
                WHERE customer_id = ? AND id = ?
                """,
                (status, confirmed_at, utc_now_text(), customer_id, memory_id),
            )
        return self.get(customer_id, memory_id)

    def delete(self, customer_id: int, memory_id: int) -> bool:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM customer_memories WHERE customer_id = ? AND id = ?",
                (customer_id, memory_id),
            )
            return cursor.rowcount > 0
