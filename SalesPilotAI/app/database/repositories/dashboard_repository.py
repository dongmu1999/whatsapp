"""工作台的真实数据库统计与最近记录查询。"""

from __future__ import annotations

from dataclasses import dataclass

from app.database.connection import Database

HIGH_INTENT_THRESHOLD = 70


@dataclass(frozen=True)
class DashboardSummary:
    total_customers: int
    today_analyses: int
    high_intent_customers: int
    pending_followup_customers: int


class DashboardRepository:
    def __init__(self, database: Database):
        self.database = database

    def get_summary(self) -> DashboardSummary:
        row = self.database.connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM customers) AS total_customers,
                (SELECT COUNT(*) FROM analyses
                 WHERE date(created_at) = date('now', 'localtime')) AS today_analyses,
                (SELECT COUNT(*) FROM customers WHERE intent_score >= ?)
                    AS high_intent_customers,
                (SELECT COUNT(DISTINCT customer_id) FROM followups
                 WHERE status = 'pending') AS pending_followup_customers
            """,
            (HIGH_INTENT_THRESHOLD,),
        ).fetchone()
        return DashboardSummary(
            total_customers=int(row["total_customers"]),
            today_analyses=int(row["today_analyses"]),
            high_intent_customers=int(row["high_intent_customers"]),
            pending_followup_customers=int(row["pending_followup_customers"]),
        )

    def get_recent_analyses(self, limit: int = 5) -> list[dict]:
        rows = self.database.connection.execute(
            """
            SELECT a.id, c.name AS customer_name, a.customer_intent,
                   a.purchase_intent_score, a.sales_stage, a.status, a.created_at
            FROM analyses AS a
            JOIN customers AS c ON c.id = a.customer_id
            ORDER BY a.created_at DESC, a.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_recent_customers(self, limit: int = 5) -> list[dict]:
        rows = self.database.connection.execute(
            """
            SELECT id, name, company_name, country, sales_stage, intent_score,
                   COALESCE(last_contact_at, created_at) AS contact_time
            FROM customers
            ORDER BY contact_time DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_upcoming_followups(self, limit: int = 5) -> list[dict]:
        rows = self.database.connection.execute(
            """
            SELECT f.id, c.name AS customer_name, f.due_at, f.priority,
                   f.content, f.status
            FROM followups AS f
            JOIN customers AS c ON c.id = f.customer_id
            WHERE f.status = 'pending'
            ORDER BY f.due_at ASC, f.id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
