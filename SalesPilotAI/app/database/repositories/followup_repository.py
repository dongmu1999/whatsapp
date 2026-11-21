"""跟进任务的本地持久化与状态更新。"""

from __future__ import annotations

from app.database.connection import Database
from app.models.followup import Followup

_BASE_SELECT = """
SELECT f.id, f.customer_id, f.analysis_id, f.due_at, f.reason, f.priority,
       f.content, f.result, f.status, f.completed_at, f.cancelled_at,
       f.created_at, f.updated_at, c.name AS customer_name
FROM followups AS f
JOIN customers AS c ON c.id = f.customer_id
"""

_ORDER = """
ORDER BY CASE f.status
             WHEN 'pending' THEN 0
             WHEN 'completed' THEN 1
             ELSE 2
         END,
         f.due_at ASC,
         f.id ASC
"""


class FollowupRepository:
    def __init__(self, database: Database):
        self.database = database

    def customer_exists(self, customer_id: int) -> bool:
        return (
            self.database.connection.execute(
                "SELECT 1 FROM customers WHERE id = ?", (customer_id,)
            ).fetchone()
            is not None
        )

    def create(
        self,
        customer_id: int,
        due_at: str,
        reason: str,
        priority: str,
        content: str,
        *,
        analysis_id: int | None = None,
    ) -> int:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO followups(
                    customer_id, analysis_id, due_at, reason, priority, content
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (customer_id, analysis_id, due_at, reason, priority, content),
            )
            return int(cursor.lastrowid)

    def get(self, followup_id: int) -> Followup | None:
        row = self.database.connection.execute(
            _BASE_SELECT + " WHERE f.id = ?", (followup_id,)
        ).fetchone()
        return None if row is None else Followup.from_row(row)

    def list(
        self,
        *,
        customer_id: int | None = None,
        status: str | None = None,
    ) -> list[Followup]:
        clauses = []
        parameters: list[object] = []
        if customer_id is not None:
            clauses.append("f.customer_id = ?")
            parameters.append(customer_id)
        if status is not None:
            clauses.append("f.status = ?")
            parameters.append(status)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.database.connection.execute(
            _BASE_SELECT + where + _ORDER, parameters
        ).fetchall()
        return [Followup.from_row(row) for row in rows]

    def pending_due_before(self, due_at: str) -> list[Followup]:
        rows = self.database.connection.execute(
            _BASE_SELECT + " WHERE f.status = 'pending' AND f.due_at < ?" + _ORDER,
            (due_at,),
        ).fetchall()
        return [Followup.from_row(row) for row in rows]

    def pending_due_between(self, start: str, end: str) -> list[Followup]:
        rows = self.database.connection.execute(
            _BASE_SELECT
            + " WHERE f.status = 'pending' AND f.due_at >= ? AND f.due_at < ?"
            + _ORDER,
            (start, end),
        ).fetchall()
        return [Followup.from_row(row) for row in rows]

    def record_result(self, followup_id: int, result: str) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE followups
                SET result = ?,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                (result, followup_id),
            )

    def complete(self, followup_id: int, result: str, completed_at: str) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE followups
                SET result = COALESCE(NULLIF(?, ''), result),
                    status = 'completed',
                    completed_at = ?,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                (result, completed_at, followup_id),
            )

    def cancel(self, followup_id: int, cancelled_at: str) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE followups
                SET status = 'cancelled',
                    cancelled_at = ?,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                (cancelled_at, followup_id),
            )
