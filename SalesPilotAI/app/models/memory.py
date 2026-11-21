"""客户长期记忆：分类、结构与本地校验。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MemoryCategory = Literal[
    "company_background",
    "business_scope",
    "interested_products",
    "purchase_quantity",
    "target_price",
    "historical_quote",
    "price_sensitivity",
    "key_objection",
    "core_concern",
    "purchase_plan",
    "communication_preference",
    "cooperation_result",
    "important_commitment",
    "next_opportunity",
    "other",
]

MEMORY_CATEGORIES = (
    ("company_background", "客户公司背景"),
    ("business_scope", "客户经营业务"),
    ("interested_products", "感兴趣产品"),
    ("purchase_quantity", "采购数量"),
    ("target_price", "目标价格"),
    ("historical_quote", "历史报价"),
    ("price_sensitivity", "价格敏感度"),
    ("key_objection", "重要异议"),
    ("core_concern", "核心顾虑"),
    ("purchase_plan", "采购计划"),
    ("communication_preference", "沟通偏好"),
    ("cooperation_result", "历史合作结果"),
    ("important_commitment", "重要承诺"),
    ("next_opportunity", "下一步销售机会"),
    ("other", "其他"),
)
CATEGORY_LABELS = dict(MEMORY_CATEGORIES)
SOURCE_LABELS = {
    "manual": "手动添加",
    "ai_suggested": "AI 建议",
    "customer_confirmed": "客户确认",
}
STATUS_LABELS = {"pending": "待确认", "confirmed": "已确认", "rejected": "已忽略"}


class MemoryValidationError(ValueError):
    """记忆内容不满足本地保存条件。"""


class MemoryNotFoundError(LookupError):
    """记忆不存在，或不属于指定客户。"""


class MemorySuggestion(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    category: MemoryCategory
    content: str = Field(min_length=1)
    evidence: str = ""

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("记忆内容不能为空")
        return value


@dataclass(frozen=True, slots=True)
class CustomerMemory:
    id: int
    customer_id: int
    category: str
    content: str
    source: str
    status: str
    confirmed_at: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row) -> "CustomerMemory":
        return cls(
            id=int(row["id"]),
            customer_id=int(row["customer_id"]),
            category=str(row["category"]),
            content=str(row["content"]),
            source=str(row["source"]),
            status=str(row["status"]),
            confirmed_at=row["confirmed_at"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )


def normalize_category(category: str) -> str:
    value = str(category or "").strip()
    if value not in CATEGORY_LABELS:
        raise MemoryValidationError("请选择有效的记忆分类")
    return value


def validate_content(content: str) -> str:
    value = " ".join(str(content or "").split())
    if not value:
        raise MemoryValidationError("记忆内容不能为空")
    if len(value) > 2000:
        raise MemoryValidationError("记忆内容不能超过 2000 个字符")
    return value


def normalize_content(content: str) -> str:
    return " ".join(str(content or "").split()).casefold()
