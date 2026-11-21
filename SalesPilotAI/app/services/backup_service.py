"""本地数据备份与恢复：ZIP 归档、完整性校验和安全回滚。"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from app.config import APP_VERSION
from app.database.connection import Database
from app.database.migrations import MIGRATIONS

logger = logging.getLogger(__name__)

LATEST_SCHEMA_VERSION = max(migration.version for migration in MIGRATIONS)
REQUIRED_TABLES = {
    "database_migrations",
    "customers",
    "conversations",
    "messages",
    "analyses",
    "knowledge_documents",
    "followups",
    "settings",
}
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


class BackupError(RuntimeError):
    """备份或恢复失败，消息可直接展示给用户。"""


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    created_at: str
    app_version: str
    schema_version: int
    database_size: int
    knowledge_files: int


@dataclass(frozen=True)
class RestoreResult:
    source: Path
    safety_backup: Path
    schema_version: int


class BackupService:
    """把数据库和知识库文件打包为可校验的 ZIP，并支持事务式恢复。"""

    FORMAT_VERSION = 1
    MAX_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
    DEFAULT_PREFIX = "salespilot-backup"
    SAFETY_PREFIX = "salespilot-pre-restore"

    def __init__(
        self,
        database: Database,
        data_dir: str | Path,
        *,
        settings=None,
    ):
        self.database = database
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.settings = settings
        self._backup_dir: Path | None = None

    @property
    def default_backup_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def backup_dir(self) -> Path:
        if self.settings is not None:
            value = self.settings.get("backup_dir")
            if value:
                return Path(value).expanduser().resolve()
            return self.default_backup_dir
        return self._backup_dir or self.default_backup_dir

    def set_backup_dir(self, path: str | Path) -> Path:
        target = Path(path).expanduser().resolve()
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise BackupError(f"无法创建备份目录：{exc}") from exc
        self._backup_dir = target
        if self.settings is not None:
            self.settings.set("backup_dir", str(target))
        return target

    def create_backup(self, destination: str | Path | None = None) -> BackupInfo:
        target_dir = (
            Path(destination).expanduser().resolve()
            if destination is not None
            else self.backup_dir
        )
        return self._write_backup(target_dir, self.DEFAULT_PREFIX)

    def inspect(self, archive: str | Path) -> BackupInfo:
        info, _, _ = self._read_archive(Path(archive).expanduser())
        return info

    def restore_backup(self, archive: str | Path) -> RestoreResult:
        source = Path(archive).expanduser()
        info, manifest, members = self._read_archive(source)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(prefix=".salespilot-restore-", dir=str(self.data_dir))
        )
        try:
            staged_db = staging / "salespilot.db"
            budget = [self.MAX_UNCOMPRESSED_BYTES]
            self._extract_member(
                source, self._database_member(manifest), staged_db, budget
            )
            self._verify_database(staged_db, manifest)
            staged_knowledge = staging / "knowledge"
            self._extract_knowledge(source, members, staged_knowledge, budget)

            rollback_snapshot = staging / "rollback.db"
            try:
                self._snapshot_database(rollback_snapshot)
            except Exception as exc:
                raise BackupError(f"无法创建恢复前数据快照：{exc}") from exc

            safety = self._write_backup(self.backup_dir, self.SAFETY_PREFIX)

            knowledge_dir = self.data_dir / "knowledge"
            old_knowledge = staging / "knowledge-old"
            had_knowledge = knowledge_dir.exists()
            try:
                if had_knowledge:
                    shutil.move(str(knowledge_dir), str(old_knowledge))
                if staged_knowledge.exists():
                    shutil.copytree(staged_knowledge, knowledge_dir)
                else:
                    knowledge_dir.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                self._rollback_knowledge(old_knowledge, knowledge_dir)
                raise BackupError(f"恢复知识库文件失败：{exc}") from exc

            try:
                if self._is_memory_database:
                    self._replace_memory_database(staged_db)
                else:
                    self._replace_file_database(staged_db)
            except Exception as exc:
                logger.exception("恢复数据库失败，尝试回滚")
                try:
                    if self._is_memory_database:
                        self._replace_memory_database(rollback_snapshot)
                    else:
                        self._replace_file_database(rollback_snapshot)
                except Exception:
                    logger.exception("恢复失败后回滚数据库也失败")
                self._rollback_knowledge(old_knowledge, knowledge_dir)
                raise BackupError(
                    f"恢复数据库失败，已回滚到恢复前的数据：{exc}"
                ) from exc

            logger.info("已从备份恢复：%s", source)
            return RestoreResult(
                source=source.resolve(),
                safety_backup=safety.path,
                schema_version=info.schema_version,
            )
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    @property
    def _is_memory_database(self) -> bool:
        return self.database.path == ":memory:"

    def _write_backup(self, target_dir: Path, prefix: str) -> BackupInfo:
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise BackupError(f"无法创建备份目录：{exc}") from exc

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = self._unique_path(target_dir, prefix, stamp)
        snapshot_path: Path | None = None
        try:
            descriptor, snapshot_name = tempfile.mkstemp(
                prefix="salespilot-snapshot-", suffix=".db"
            )
            os.close(descriptor)
            snapshot_path = Path(snapshot_name)
            self._snapshot_database(snapshot_path)
            database_bytes = snapshot_path.read_bytes()
            checksum = hashlib.sha256(database_bytes).hexdigest()
            knowledge_files = self._knowledge_files()
            manifest = {
                "format_version": self.FORMAT_VERSION,
                "app_version": APP_VERSION,
                "created_at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "schema_version": self._schema_version(),
                "database": {
                    "file": "salespilot.db",
                    "sha256": checksum,
                    "size": len(database_bytes),
                },
                "knowledge": {"files": len(knowledge_files)},
            }
            with zipfile.ZipFile(
                path, "w", compression=zipfile.ZIP_DEFLATED
            ) as bundle:
                bundle.writestr(
                    "manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2),
                )
                bundle.write(snapshot_path, "salespilot.db")
                for file in knowledge_files:
                    bundle.write(file, self._knowledge_arcname(file))
        except BackupError:
            path.unlink(missing_ok=True)
            raise
        except (OSError, sqlite3.Error) as exc:
            path.unlink(missing_ok=True)
            logger.exception("创建备份失败")
            raise BackupError(f"创建备份失败：{exc}") from exc
        finally:
            if snapshot_path is not None:
                snapshot_path.unlink(missing_ok=True)

        logger.info("已创建数据备份：%s", path)
        return BackupInfo(
            path=path,
            created_at=manifest["created_at"],
            app_version=APP_VERSION,
            schema_version=manifest["schema_version"],
            database_size=len(database_bytes),
            knowledge_files=len(knowledge_files),
        )

    def _read_archive(self, path: Path):
        if not path.is_file():
            raise BackupError(f"备份文件不存在：{path}")
        try:
            with zipfile.ZipFile(path) as bundle:
                members = bundle.infolist()
                for member in members:
                    self._entry_parts(member.filename)
                total_size = sum(max(member.file_size, 0) for member in members)
                if total_size > self.MAX_UNCOMPRESSED_BYTES:
                    raise BackupError("备份包解压后体积过大，已拒绝恢复")
                names = {member.filename for member in members}
                if "manifest.json" not in names:
                    raise BackupError("备份包缺少 manifest.json，无法恢复")
                try:
                    manifest = json.loads(
                        bundle.read("manifest.json").decode("utf-8")
                    )
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise BackupError("备份清单无法解析，文件可能已损坏") from exc
        except zipfile.BadZipFile as exc:
            raise BackupError("备份文件不是有效的 ZIP 压缩包") from exc
        except OSError as exc:
            raise BackupError(f"无法读取备份文件：{exc}") from exc

        if not isinstance(manifest, dict):
            raise BackupError("备份清单格式不正确")
        format_version = manifest.get("format_version")
        if not isinstance(format_version, int) or isinstance(format_version, bool):
            raise BackupError("备份清单缺少有效的格式版本")
        if format_version > self.FORMAT_VERSION:
            raise BackupError("备份格式版本高于当前软件，请升级软件后再恢复")

        schema_version = manifest.get("schema_version")
        if not isinstance(schema_version, int) or isinstance(schema_version, bool):
            raise BackupError("备份清单缺少有效的数据库版本")
        if schema_version > LATEST_SCHEMA_VERSION:
            raise BackupError("备份数据库版本高于当前软件，无法恢复")

        database_info = manifest.get("database")
        if not isinstance(database_info, dict) or not database_info.get("sha256"):
            raise BackupError("备份清单缺少数据库校验信息")
        database_member = self._database_member(manifest)
        self._entry_parts(database_member)
        if database_member not in names:
            raise BackupError("备份包缺少数据库文件，无法恢复")

        knowledge_info = manifest.get("knowledge") or {}
        try:
            knowledge_files = int(knowledge_info.get("files", 0))
        except (TypeError, ValueError):
            knowledge_files = 0

        info = BackupInfo(
            path=path.resolve(),
            created_at=str(manifest.get("created_at", "")),
            app_version=str(manifest.get("app_version", "")),
            schema_version=schema_version,
            database_size=int(database_info.get("size", 0) or 0),
            knowledge_files=knowledge_files,
        )
        return info, manifest, members

    @staticmethod
    def _database_member(manifest: dict) -> str:
        value = manifest.get("database", {}).get("file", "salespilot.db")
        return str(value or "salespilot.db")

    @classmethod
    def _entry_parts(cls, name: str) -> tuple[str, ...]:
        normalized = name.replace("\\", "/")
        if normalized.startswith("/") or PurePosixPath(normalized).is_absolute():
            raise BackupError("备份包包含不安全的文件路径，已拒绝恢复")
        parts = tuple(
            part
            for part in PurePosixPath(normalized).parts
            if part not in ("", ".")
        )
        if any(part == ".." for part in parts):
            raise BackupError("备份包包含不安全的文件路径，已拒绝恢复")
        if parts and _DRIVE_PREFIX.match(parts[0]):
            raise BackupError("备份包包含不安全的文件路径，已拒绝恢复")
        return parts

    def _verify_database(self, staged_db: Path, manifest: dict) -> None:
        expected = str(manifest["database"]["sha256"])
        data = staged_db.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise BackupError("备份数据库校验失败，文件可能已损坏")
        expected_size = manifest["database"].get("size")
        if isinstance(expected_size, int) and expected_size != len(data):
            raise BackupError("备份数据库大小与清单不一致，文件可能已损坏")

        connection = sqlite3.connect(staged_db)
        try:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            if not result or str(result[0]).casefold() != "ok":
                raise BackupError("备份数据库完整性检查失败，文件可能已损坏")
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
        except sqlite3.DatabaseError as exc:
            raise BackupError("备份数据库损坏或不是有效的 SQLite 数据库") from exc
        finally:
            connection.close()

        if REQUIRED_TABLES - tables:
            raise BackupError("备份数据库缺少必要的数据表，无法恢复")

    def _extract_member(
        self, archive: Path, member: str, target: Path, budget: list[int] | None = None
    ) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        try:
            with zipfile.ZipFile(archive) as bundle, bundle.open(member) as source:
                with target.open("wb") as destination:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if budget is not None and total > budget[0]:
                            raise BackupError(
                                "备份包解压后体积过大，已拒绝恢复"
                            )
                        destination.write(chunk)
        except (OSError, zipfile.BadZipFile) as exc:
            raise BackupError(f"解压备份文件失败：{exc}") from exc
        if budget is not None:
            budget[0] -= total

    def _extract_knowledge(
        self, archive: Path, members, target_dir: Path, budget: list[int] | None = None
    ) -> None:
        for member in members:
            parts = self._entry_parts(member.filename)
            if not parts or parts[0] != "knowledge" or len(parts) < 2:
                continue
            relative = parts[1:]
            target = target_dir.joinpath(*relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            self._extract_member(archive, member.filename, target, budget)

    def _snapshot_database(self, target: Path) -> None:
        connection = sqlite3.connect(target)
        try:
            self.database.connection.backup(connection)
        finally:
            connection.close()

    def _schema_version(self) -> int:
        row = self.database.connection.execute(
            "SELECT max(version) FROM database_migrations"
        ).fetchone()
        value = row[0] if row else None
        if value is None:
            value = self.database.connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
        return int(value or 0)

    def _knowledge_files(self) -> list[Path]:
        directory = self.data_dir / "knowledge"
        if not directory.is_dir():
            return []
        return sorted(path for path in directory.rglob("*") if path.is_file())

    def _knowledge_arcname(self, path: Path) -> str:
        return f"knowledge/{path.relative_to(self.data_dir / 'knowledge').as_posix()}"

    @staticmethod
    def _unique_path(target_dir: Path, prefix: str, stamp: str) -> Path:
        candidate = target_dir / f"{prefix}-{stamp}.zip"
        index = 1
        while candidate.exists():
            candidate = target_dir / f"{prefix}-{stamp}-{index}.zip"
            index += 1
        return candidate

    def _replace_file_database(self, source: Path) -> None:
        db_path = Path(self.database.path).expanduser()
        if not db_path.is_absolute():
            db_path = (Path.cwd() / db_path).resolve()
        self.database.close()
        for candidate in (
            db_path,
            Path(f"{db_path}-wal"),
            Path(f"{db_path}-shm"),
        ):
            try:
                candidate.unlink(missing_ok=True)
            except OSError as exc:
                raise BackupError(f"无法替换数据库文件：{exc}") from exc
        shutil.copy2(source, db_path)
        self.database.reconnect()
        self.database.initialize()

    def _replace_memory_database(self, source: Path) -> None:
        connection = sqlite3.connect(source)
        try:
            connection.backup(self.database.connection)
        finally:
            connection.close()
        self.database.initialize()

    @staticmethod
    def _rollback_knowledge(old_knowledge: Path, knowledge_dir: Path) -> None:
        try:
            if knowledge_dir.exists():
                shutil.rmtree(knowledge_dir, ignore_errors=True)
            if old_knowledge.exists():
                shutil.move(str(old_knowledge), str(knowledge_dir))
            else:
                knowledge_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.exception("回滚知识库目录失败")
