"""应用设置的本地持久化。"""

from __future__ import annotations

from app.database.connection import Database


class SettingsRepository:
    def __init__(self, database: Database):
        self.database = database

    def get(self, key: str, default: str | None = None) -> str | None:
        row = self.database.connection.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return default if row is None else str(row["value"])

    def set(self, key: str, value: str) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO settings(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                """,
                (key, value),
            )
