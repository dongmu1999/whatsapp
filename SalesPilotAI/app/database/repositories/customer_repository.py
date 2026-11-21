"""客户档案的 SQLite 增删改查、搜索筛选和排序。"""

from __future__ import annotations

from collections.abc import Mapping

from app.database.connection import Database
from app.models.customer import Customer, EDITABLE_FIELDS, normalize_customer_data

_SEARCH_FIELDS = (
    "name",
    "company_name",
    "contact_info",
    "whatsapp_number",
    "email",
    "interested_products",
)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class CustomerRepository:
    def __init__(self, database: Database):
        self.database = database

    def create(self, data: Mapping[str, object]) -> Customer:
        normalized = normalize_customer_data(data)
        placeholders = ", ".join("?" for _ in EDITABLE_FIELDS)
        columns = ", ".join(EDITABLE_FIELDS)
        values = [normalized[field] for field in EDITABLE_FIELDS]
        with self.database.transaction() as connection:
            cursor = connection.execute(
                f"INSERT INTO customers({columns}) VALUES ({placeholders})", values
            )
            row = connection.execute(
                "SELECT * FROM customers WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return Customer.from_row(row)

    def get(self, customer_id: int) -> Customer | None:
        row = self.database.connection.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        return Customer.from_row(row) if row is not None else None

    def update(self, customer_id: int, data: Mapping[str, object]) -> Customer:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM customers WHERE id = ?", (customer_id,)
            ).fetchone()
            if row is None:
                raise KeyError("客户不存在或已被删除")
            merged = Customer.from_row(row).as_dict()
            merged.update(data)
            normalized = normalize_customer_data(merged)
            assignments = ", ".join(f"{field} = ?" for field in EDITABLE_FIELDS)
            values = [normalized[field] for field in EDITABLE_FIELDS]
            connection.execute(
                f"""
                UPDATE customers
                SET {assignments},
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                [*values, customer_id],
            )
            updated = connection.execute(
                "SELECT * FROM customers WHERE id = ?", (customer_id,)
            ).fetchone()
        return Customer.from_row(updated)

    def delete(self, customer_id: int) -> bool:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM customers WHERE id = ?", (customer_id,)
            )
        return cursor.rowcount > 0

    def list(
        self,
        search: str = "",
        country: str = "",
        sales_stage: str = "",
        sort_by: str = "last_contact",
        descending: bool = True,
    ) -> list[Customer]:
        if sort_by not in {"last_contact", "intent_score"}:
            raise ValueError("不支持的客户排序方式")

        conditions: list[str] = []
        parameters: list[object] = []
        search = search.strip()
        if search:
            escaped = _escape_like(search)
            search_conditions = []
            for field in _SEARCH_FIELDS:
                search_conditions.append(
                    f"COALESCE({field}, '') LIKE ? ESCAPE '\\'"
                )
                parameters.append(f"%{escaped}%")
            conditions.append("(" + " OR ".join(search_conditions) + ")")
        if country:
            conditions.append("country = ?")
            parameters.append(country)
        if sales_stage:
            conditions.append("sales_stage = ?")
            parameters.append(sales_stage)

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        direction = "DESC" if descending else "ASC"
        if sort_by == "intent_score":
            order_by = f"intent_score {direction}, id DESC"
        else:
            order_by = (
                "last_contact_at IS NULL ASC, "
                f"last_contact_at {direction}, created_at DESC, id DESC"
            )
        rows = self.database.connection.execute(
            f"SELECT * FROM customers{where} ORDER BY {order_by}", parameters
        ).fetchall()
        return [Customer.from_row(row) for row in rows]

    def countries(self) -> list[str]:
        rows = self.database.connection.execute(
            """
            SELECT DISTINCT country FROM customers
            WHERE country IS NOT NULL AND TRIM(country) <> ''
            ORDER BY country COLLATE NOCASE ASC
            """
        ).fetchall()
        return [row["country"] for row in rows]
