"""客户档案业务服务，以及 CSV/Excel 导入导出。"""

from __future__ import annotations

import csv
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping
from zipfile import BadZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from app.database.repositories.customer_repository import CustomerRepository
from app.models.customer import (
    CUSTOMER_FIELDS,
    Customer,
    CustomerValidationError,
    FIELD_LABELS,
)

logger = logging.getLogger(__name__)

_HEADER_TO_FIELD = {
    **{field: field for field in CUSTOMER_FIELDS},
    **{label: field for field, label in FIELD_LABELS.items()},
}


class CustomerImportError(ValueError):
    """客户文件无法读取、解析或写入。"""


@dataclass
class ImportResult:
    imported: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.imported + self.failed


class CustomerService:
    def __init__(self, repository: CustomerRepository):
        self.repository = repository

    def create(self, data: Mapping[str, object]) -> Customer:
        return self.repository.create(data)

    def get(self, customer_id: int) -> Customer | None:
        return self.repository.get(customer_id)

    def update(self, customer_id: int, data: Mapping[str, object]) -> Customer:
        return self.repository.update(customer_id, data)

    def delete(self, customer_id: int) -> bool:
        return self.repository.delete(customer_id)

    def list(self, **filters) -> list[Customer]:
        return self.repository.list(**filters)

    def countries(self) -> list[str]:
        return self.repository.countries()

    def import_file(self, file_path: str | Path) -> ImportResult:
        path = Path(file_path)
        rows = self._read_rows(path)
        result = ImportResult()
        for row_number, data in rows:
            try:
                self.repository.create(data)
            except CustomerValidationError as exc:
                result.failed += 1
                result.errors.append(f"第 {row_number} 行：{exc}")
            except sqlite3.Error:
                result.failed += 1
                result.errors.append(f"第 {row_number} 行：数据库写入失败，请稍后重试")
                logger.exception("导入客户时数据库写入失败：%s", path)
            else:
                result.imported += 1
        return result

    def export_file(
        self, file_path: str | Path, customers: Iterable[Customer] | None = None
    ) -> int:
        path = Path(file_path)
        suffix = path.suffix.lower()
        rows = list(customers) if customers is not None else self.repository.list()
        try:
            if suffix == ".csv":
                self._export_csv(path, rows)
            elif suffix in {".xlsx", ".xlsm"}:
                self._export_excel(path, rows)
            else:
                raise CustomerImportError("仅支持导出 CSV 或 Excel (.xlsx) 文件")
        except CustomerImportError:
            raise
        except (OSError, ValueError, InvalidFileException) as exc:
            logger.exception("导出客户失败：%s", path)
            raise CustomerImportError("导出失败，请检查文件路径和写入权限") from exc
        return len(rows)

    def _read_rows(self, path: Path) -> list[tuple[int, dict]]:
        suffix = path.suffix.lower()
        try:
            if suffix == ".csv":
                return self._read_csv(path)
            if suffix in {".xlsx", ".xlsm"}:
                return self._read_excel(path)
            raise CustomerImportError("仅支持导入 CSV 或 Excel (.xlsx) 文件")
        except CustomerImportError:
            raise
        except (OSError, UnicodeError, csv.Error, BadZipFile, InvalidFileException, ValueError) as exc:
            logger.exception("读取客户导入文件失败：%s", path)
            raise CustomerImportError("无法读取导入文件，请确认文件存在、格式正确且未损坏") from exc

    @staticmethod
    def _map_headers(headers) -> dict[int, str]:
        mapped: dict[int, str] = {}
        for index, header in enumerate(headers):
            key = str(header or "").strip()
            field_name = _HEADER_TO_FIELD.get(key)
            if field_name in FIELD_LABELS:
                mapped[index] = field_name
        if "name" not in mapped.values():
            raise CustomerImportError("导入文件缺少“客户姓名”列")
        return mapped

    @staticmethod
    def _is_empty_row(values) -> bool:
        return all(value is None or not str(value).strip() for value in values)

    def _read_csv(self, path: Path) -> list[tuple[int, dict]]:
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                return self._rows_from_csv(handle)
        except UnicodeDecodeError:
            with path.open("r", encoding="gb18030", newline="") as handle:
                return self._rows_from_csv(handle)

    def _rows_from_csv(self, handle) -> list[tuple[int, dict]]:
        reader = csv.reader(handle)
        headers = next(reader, None)
        if headers is None:
            raise CustomerImportError("导入文件为空或缺少表头")
        header_map = self._map_headers(headers)
        rows = []
        for row_number, values in enumerate(reader, start=2):
            if self._is_empty_row(values):
                continue
            data = {
                field_name: values[index] if index < len(values) else None
                for index, field_name in header_map.items()
            }
            rows.append((row_number, data))
        return rows

    def _read_excel(self, path: Path) -> list[tuple[int, dict]]:
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = workbook.active
            iterator = sheet.iter_rows(values_only=True)
            headers = next(iterator, None)
            if headers is None:
                raise CustomerImportError("导入文件为空或缺少表头")
            header_map = self._map_headers(headers)
            rows = []
            for row_number, values in enumerate(iterator, start=2):
                if self._is_empty_row(values):
                    continue
                data = {
                    field_name: values[index] if index < len(values) else None
                    for index, field_name in header_map.items()
                }
                rows.append((row_number, data))
            return rows
        finally:
            workbook.close()

    @staticmethod
    def _export_csv(path: Path, customers: list[Customer]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([FIELD_LABELS[field] for field in CUSTOMER_FIELDS])
            for customer in customers:
                values = customer.as_dict()
                writer.writerow([values[field] for field in CUSTOMER_FIELDS])

    @staticmethod
    def _export_excel(path: Path, customers: list[Customer]) -> None:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "客户档案"
        sheet.append([FIELD_LABELS[field] for field in CUSTOMER_FIELDS])
        for customer in customers:
            values = customer.as_dict()
            sheet.append([values[field] for field in CUSTOMER_FIELDS])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        workbook.save(path)
        workbook.close()
