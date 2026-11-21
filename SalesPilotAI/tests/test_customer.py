from __future__ import annotations

import csv
from datetime import datetime

import pytest
from openpyxl import load_workbook

from app.database import Database
from app.database.repositories.customer_repository import CustomerRepository
from app.models.customer import EDITABLE_FIELDS, CustomerValidationError
from app.services.customer_service import CustomerImportError, CustomerService


@pytest.fixture
def service(database):
    return CustomerService(CustomerRepository(database))


def full_customer_data(**overrides):
    data = {
        "name": "Alice Smith",
        "company_name": "Globex Trading GmbH",
        "country": "Germany",
        "contact_info": "+49 170 0000001",
        "whatsapp_number": "+491700000001",
        "email": "alice@globex.example",
        "website": "https://globex.example",
        "customer_type": "进口商",
        "interested_products": "Industrial valves, Pumps",
        "expected_quantity": "500 units",
        "target_price": "USD 20 / unit",
        "historical_quotes": "2026-10 quote: USD 22 / unit",
        "purchase_history": "2025 ordered 100 units",
        "sales_stage": "Negotiation",
        "intent_score": 86,
        "core_concerns": "交期与产品认证",
        "notes": "偏好英文邮件沟通",
        "first_contact_at": "2026-10-01T08:30:00Z",
        "last_contact_at": "2026-11-20T10:00:00Z",
        "next_followup_at": "2026-11-25T09:00:00Z",
    }
    data.update(overrides)
    return data


def test_customer_crud_persists_every_editable_field(service):
    created = service.create(full_customer_data())

    assert created.id is not None
    assert created.created_at
    assert created.updated_at
    for field in EDITABLE_FIELDS:
        assert getattr(created, field) == full_customer_data()[field]

    updated = service.update(created.id, {"name": "Alice Cooper", "intent_score": 92})
    assert updated.name == "Alice Cooper"
    assert updated.intent_score == 92
    assert updated.company_name == "Globex Trading GmbH"
    assert service.get(created.id) == updated

    assert service.delete(created.id) is True
    assert service.get(created.id) is None
    assert service.delete(created.id) is False


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"name": "   "}, "客户姓名不能为空"),
        ({"sales_stage": "Unknown"}, "不支持的销售阶段"),
        ({"intent_score": 101}, "意向评分"),
        ({"intent_score": "high"}, "意向评分"),
        ({"last_contact_at": "not-a-date"}, "最后沟通时间格式不正确"),
    ],
)
def test_customer_validation_rejects_invalid_values(service, changes, message):
    with pytest.raises(CustomerValidationError, match=message):
        service.create(full_customer_data(**changes))


def test_search_filters_sorting_and_countries_use_real_rows(service):
    alice = service.create(
        full_customer_data(
            name="Alice",
            country="Germany",
            sales_stage="Inquiry",
            intent_score=90,
            whatsapp_number="+491111",
            last_contact_at="2026-11-20T10:00:00Z",
        )
    )
    bob = service.create(
        full_customer_data(
            name="Bob",
            company_name="Acme Imports",
            email="bob@acme.example",
            country="United States",
            sales_stage="Interested",
            intent_score=40,
            whatsapp_number="+12222",
            last_contact_at="2026-11-21T10:00:00Z",
        )
    )
    zhang = service.create(
        full_customer_data(
            name="张敏",
            company_name="Neo Trading",
            email="zhang@neo.example",
            country="Germany",
            sales_stage="Quotation",
            intent_score=70,
            whatsapp_number="+8613333",
            last_contact_at=None,
        )
    )

    assert [item.id for item in service.list(search="globex")] == [alice.id]
    assert [item.id for item in service.list(search="1111")] == [alice.id]
    assert {item.id for item in service.list(country="Germany")} == {alice.id, zhang.id}
    assert [item.id for item in service.list(sales_stage="Interested")] == [bob.id]
    assert [item.id for item in service.list(sort_by="intent_score")] == [
        alice.id,
        zhang.id,
        bob.id,
    ]
    assert [item.id for item in service.list(sort_by="intent_score", descending=False)] == [
        bob.id,
        zhang.id,
        alice.id,
    ]
    assert [item.id for item in service.list(sort_by="last_contact")] == [
        bob.id,
        alice.id,
        zhang.id,
    ]
    assert service.countries() == ["Germany", "United States"]


def test_customer_delete_cascades_related_records(service, database):
    customer = service.create(full_customer_data())
    conversation_id = database.connection.execute(
        "INSERT INTO conversations(customer_id, title) VALUES (?, 'WhatsApp')",
        (customer.id,),
    ).lastrowid
    database.connection.execute(
        "INSERT INTO followups(customer_id, due_at, content) VALUES (?, '2026-11-25T09:00:00Z', '报价跟进')",
        (customer.id,),
    )

    assert service.delete(customer.id) is True
    assert database.connection.execute(
        "SELECT COUNT(*) FROM conversations WHERE id = ?", (conversation_id,)
    ).fetchone()[0] == 0
    assert database.connection.execute(
        "SELECT COUNT(*) FROM followups WHERE customer_id = ?", (customer.id,)
    ).fetchone()[0] == 0


def test_csv_export_and_import_round_trip(service, tmp_path):
    original = service.create(full_customer_data())
    path = tmp_path / "customers.csv"

    assert service.export_file(path, [original]) == 1
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["客户姓名"] == "Alice Smith"
    assert rows[0]["意向评分"] == "86"
    assert service.delete(original.id) is True

    result = service.import_file(path)
    assert result.total == 1
    assert result.imported == 1
    assert result.failed == 0
    imported = service.list()[0]
    assert imported.company_name == "Globex Trading GmbH"
    assert imported.intent_score == 86
    assert imported.id != original.id


def test_excel_export_and_import_round_trip(service, tmp_path):
    original = service.create(full_customer_data())
    path = tmp_path / "customers.xlsx"

    assert service.export_file(path, [original]) == 1
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    assert sheet.title == "客户档案"
    assert sheet.max_row == 2
    assert sheet.cell(1, 1).value == "客户 ID"
    assert sheet.cell(1, 2).value == "客户姓名"
    workbook.close()
    assert service.delete(original.id) is True

    result = service.import_file(path)
    assert result.imported == 1
    assert result.failed == 0
    imported = service.list()[0]
    assert imported.email == "alice@globex.example"
    assert imported.next_followup_at == "2026-11-25T09:00:00Z"


def test_import_skips_invalid_rows_and_reports_chinese_errors(service, tmp_path):
    path = tmp_path / "mixed.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["name", "sales_stage", "intent_score"])
        writer.writeheader()
        writer.writerow({"name": "Valid", "sales_stage": "New Lead", "intent_score": 20})
        writer.writerow({"name": "", "sales_stage": "New Lead", "intent_score": 20})
        writer.writerow({"name": "Bad Stage", "sales_stage": "Bad", "intent_score": 20})
        writer.writerow({"name": "Bad Score", "sales_stage": "New Lead", "intent_score": 101})

    result = service.import_file(path)
    assert result.total == 4
    assert result.imported == 1
    assert result.failed == 3
    assert len(result.errors) == 3
    assert "第 3 行" in result.errors[0]
    assert "客户姓名不能为空" in result.errors[0]
    assert [customer.name for customer in service.list()] == ["Valid"]


def test_excel_import_accepts_datetime_cells(service, tmp_path):
    from openpyxl import Workbook

    path = tmp_path / "datetime.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["客户姓名", "最后沟通时间"])
    sheet.append(["Excel Customer", datetime(2026, 11, 20, 10, 30)])
    workbook.save(path)

    result = service.import_file(path)
    assert result.imported == 1
    assert service.list()[0].last_contact_at == "2026-11-20T10:30:00Z"


def test_import_requires_name_column_and_supported_format(service, tmp_path):
    missing_name = tmp_path / "missing_name.csv"
    missing_name.write_text("公司名称\nAcme\n", encoding="utf-8-sig")
    with pytest.raises(CustomerImportError, match="客户姓名"):
        service.import_file(missing_name)

    unsupported = tmp_path / "customers.txt"
    unsupported.write_text("Alice", encoding="utf-8")
    with pytest.raises(CustomerImportError, match="CSV 或 Excel"):
        service.import_file(unsupported)
