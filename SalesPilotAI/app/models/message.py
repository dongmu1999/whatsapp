"""捕获消息模型、手动文本解析、去重和数量整理。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

SENDER_TYPES = ("unknown", "customer", "sales")
CAPTURE_SOURCES = ("manual", "uia", "ocr")

_TIMESTAMP_PREFIX = re.compile(
    r"^\[?(?P<timestamp>(?:\d{1,4}[/-]){2}\d{1,4},?\s+"
    r"\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\]?\s*(?:-\s*)?(?P<body>.*)$",
    re.IGNORECASE,
)
_SENDER_PREFIX = re.compile(r"^([^:：\n]{1,120})[:：]\s*(.*)$")
_CUSTOMER_ALIASES = {"客户", "customer", "buyer"}
_SALES_ALIASES = {"我", "me", "销售", "sales", "salesperson"}


def utc_now_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class CapturedMessage:
    content: str
    sender_type: str = "unknown"
    timestamp: str | None = None
    source: str = "manual"
    recognized_at: str | None = None
    confidence: float | None = None
    sender_name: str | None = None

    def __post_init__(self) -> None:
        if not self.content or not self.content.strip():
            raise ValueError("消息内容不能为空")
        if self.sender_type not in SENDER_TYPES:
            raise ValueError("发送方必须是客户、销售或未知")
        if self.source not in CAPTURE_SOURCES:
            raise ValueError("不支持的消息来源")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("识别置信度必须在 0 到 1 之间")


class MessageParser:
    """解析 WhatsApp 导出样式及带“客户/销售”前缀的手动粘贴文本。"""

    @classmethod
    def parse(
        cls,
        text: str,
        *,
        source: str = "manual",
        customer_name: str = "",
        sales_name: str = "",
        recognized_at: str | None = None,
        confidence: float | None = None,
    ) -> list[CapturedMessage]:
        if source not in CAPTURE_SOURCES:
            raise ValueError("不支持的消息来源")
        recognized_at = recognized_at or utc_now_text()
        messages: list[CapturedMessage] = []
        for raw_line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            if not raw_line.strip():
                continue
            timestamp, sender_name, sender_type, content = cls._parse_line(
                raw_line, customer_name, sales_name
            )
            if timestamp is None and sender_name is None and messages and messages[-1].timestamp:
                previous = messages[-1]
                messages[-1] = CapturedMessage(
                    content=f"{previous.content}\n{raw_line}",
                    sender_type=previous.sender_type,
                    timestamp=previous.timestamp,
                    source=previous.source,
                    recognized_at=previous.recognized_at,
                    confidence=previous.confidence,
                    sender_name=previous.sender_name,
                )
                continue
            if not content.strip():
                continue
            messages.append(
                CapturedMessage(
                    content=content.strip(),
                    sender_type=sender_type,
                    timestamp=timestamp,
                    source=source,
                    recognized_at=recognized_at,
                    confidence=confidence,
                    sender_name=sender_name,
                )
            )
        return messages

    @staticmethod
    def _parse_line(
        line: str, customer_name: str, sales_name: str
    ) -> tuple[str | None, str | None, str, str]:
        timestamp = None
        body = line.strip()
        match = _TIMESTAMP_PREFIX.match(body)
        if match:
            timestamp = match.group("timestamp").strip()
            body = match.group("body").strip()

        sender_match = _SENDER_PREFIX.match(body)
        if not sender_match:
            return timestamp, None, "unknown", body
        sender_name = sender_match.group(1).strip()
        content = sender_match.group(2)
        folded = sender_name.casefold()
        if folded in _CUSTOMER_ALIASES or (
            customer_name.strip() and folded == customer_name.strip().casefold()
        ):
            sender_type = "customer"
        elif folded in _SALES_ALIASES or (
            sales_name.strip() and folded == sales_name.strip().casefold()
        ):
            sender_type = "sales"
        else:
            sender_type = "unknown"
        return timestamp, sender_name, sender_type, content


def prepare_messages(
    messages: Iterable[CapturedMessage], limit: int = 30
) -> list[CapturedMessage]:
    """去掉相邻重复项，保留时间顺序，并仅取最后 limit 条可见消息。"""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ValueError("消息数量必须是 1 到 200 的整数")
    deduplicated: list[CapturedMessage] = []
    previous_key = None
    for message in messages:
        key = (
            message.content,
            message.sender_type,
            message.timestamp,
            message.sender_name,
        )
        if key != previous_key:
            deduplicated.append(message)
        previous_key = key
    return deduplicated[-limit:]
