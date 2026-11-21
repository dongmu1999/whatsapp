"""客户档案模型、字段定义和输入校验。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timezone
from typing import Mapping

SALES_STAGES = (
    "New Lead",
    "Initial Contact",
    "Interested",
    "Inquiry",
    "Quotation",
    "Negotiation",
    "Sample",
    "Order",
    "Repeat Customer",
    "Lost",
)

TEXT_FIELDS = (
    "name",
    "company_name",
    "country",
    "contact_info",
    "whatsapp_number",
    "email",
    "website",
    "customer_type",
    "interested_products",
    "expected_quantity",
    "target_price",
    "historical_quotes",
    "purchase_history",
    "core_concerns",
    "notes",
)
TIMESTAMP_FIELDS = ("first_contact_at", "last_contact_at", "next_followup_at")
EDITABLE_FIELDS = (
    "name",
    "company_name",
    "country",
    "contact_info",
    "whatsapp_number",
    "email",
    "website",
    "customer_type",
    "interested_products",
    "expected_quantity",
    "target_price",
    "historical_quotes",
    "purchase_history",
    "sales_stage",
    "intent_score",
    "core_concerns",
    "notes",
    "first_contact_at",
    "last_contact_at",
    "next_followup_at",
)
CUSTOMER_FIELDS = ("id",) + EDITABLE_FIELDS + ("created_at", "updated_at")

FIELD_LABELS = {
    "id": "客户 ID",
    "name": "客户姓名",
    "company_name": "公司名称",
    "country": "国家",
    "contact_info": "联系方式",
    "whatsapp_number": "WhatsApp 号码",
    "email": "邮箱",
    "website": "公司网站",
    "customer_type": "客户类型",
    "interested_products": "感兴趣产品",
    "expected_quantity": "预计采购数量",
    "target_price": "目标价格",
    "historical_quotes": "历史报价",
    "purchase_history": "采购历史",
    "sales_stage": "当前销售阶段",
    "intent_score": "意向评分",
    "core_concerns": "客户核心顾虑",
    "notes": "客户备注",
    "first_contact_at": "首次联系时间",
    "last_contact_at": "最后沟通时间",
    "next_followup_at": "下次跟进时间",
    "created_at": "创建时间",
    "updated_at": "更新时间",
}


class CustomerValidationError(ValueError):
    """客户输入不符合档案约束。"""


@dataclass(frozen=True)
class Customer:
    name: str
    company_name: str | None = None
    country: str | None = None
    contact_info: str | None = None
    whatsapp_number: str | None = None
    email: str | None = None
    website: str | None = None
    customer_type: str | None = None
    interested_products: str | None = None
    expected_quantity: str | None = None
    target_price: str | None = None
    historical_quotes: str | None = None
    purchase_history: str | None = None
    sales_stage: str = "New Lead"
    intent_score: int = 0
    core_concerns: str | None = None
    notes: str | None = None
    first_contact_at: str | None = None
    last_contact_at: str | None = None
    next_followup_at: str | None = None
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @classmethod
    def from_row(cls, row) -> "Customer":
        return cls(**{field: row[field] for field in CUSTOMER_FIELDS})

    def as_dict(self) -> dict:
        return asdict(self)


def _normalize_timestamp(value, field: str) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, date):
            parsed = datetime.combine(value, time.min)
        else:
            text = str(value).strip()
            if text.endswith(("Z", "z")):
                text = text[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        parsed = parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError) as exc:
        raise CustomerValidationError(
            f"{FIELD_LABELS[field]}格式不正确，请使用 ISO 时间，例如 2026-11-21T09:30:00Z"
        ) from exc
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_customer_data(data: Mapping[str, object]) -> dict:
    """清理输入并返回可写入 customers 表的完整字段。"""
    normalized: dict[str, object] = {}
    for field in TEXT_FIELDS:
        value = data.get(field)
        text = "" if value is None else str(value).strip()
        normalized[field] = text or None

    if not normalized["name"]:
        raise CustomerValidationError("客户姓名不能为空")

    stage = str(data.get("sales_stage") or "New Lead").strip()
    if stage not in SALES_STAGES:
        raise CustomerValidationError(f"不支持的销售阶段：{stage}")
    normalized["sales_stage"] = stage

    score = data.get("intent_score", 0)
    if score is None or (isinstance(score, str) and not score.strip()):
        score = 0
    try:
        if isinstance(score, bool):
            raise ValueError
        normalized["intent_score"] = int(score)
    except (TypeError, ValueError, OverflowError) as exc:
        raise CustomerValidationError("意向评分必须是 0 到 100 的整数") from exc
    if not 0 <= normalized["intent_score"] <= 100:
        raise CustomerValidationError("意向评分必须是 0 到 100 的整数")

    for field in TIMESTAMP_FIELDS:
        normalized[field] = _normalize_timestamp(data.get(field), field)

    return {field: normalized[field] for field in EDITABLE_FIELDS}
