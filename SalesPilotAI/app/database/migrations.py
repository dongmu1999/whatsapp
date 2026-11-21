"""按版本执行、可重复运行的数据库迁移。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.database.schema import INITIAL_SCHEMA, KNOWLEDGE_SEARCH_SCHEMA


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str


MIGRATIONS = (
    Migration(1, "initial_schema", INITIAL_SCHEMA),
    Migration(2, "knowledge_full_text_search", KNOWLEDGE_SEARCH_SCHEMA),
)


class MigrationManager:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def migrate(self) -> list[int]:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS database_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT (
                    strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                )
            )
            """
        )
        self.connection.commit()

        applied = {
            row["version"]
            for row in self.connection.execute(
                "SELECT version FROM database_migrations"
            ).fetchall()
        }
        applied_now: list[int] = []

        for migration in sorted(MIGRATIONS, key=lambda item: item.version):
            if migration.version in applied:
                continue
            self._apply(migration)
            applied_now.append(migration.version)

        return applied_now

    def _apply(self, migration: Migration) -> None:
        escaped_name = migration.name.replace("'", "''")
        script = f"""
BEGIN IMMEDIATE;
{migration.sql}
INSERT INTO database_migrations(version, name)
VALUES ({migration.version}, '{escaped_name}');
PRAGMA user_version = {migration.version};
COMMIT;
"""
        try:
            self.connection.executescript(script)
        except Exception:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise
