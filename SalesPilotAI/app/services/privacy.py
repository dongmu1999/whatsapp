"""上传前本地脱敏；只处理用户明确选择的消息副本。"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Iterable

from app.models.message import CapturedMessage

_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<![\w@])\+?\d[\d\s().-]{5,}\d(?![\w@])")


def redact_text(text: str, company_names: Iterable[str] = ()) -> str:
    redacted = _EMAIL.sub("[已脱敏邮箱]", str(text))

    def replace_phone(match):
        value = match.group(0)
        digits = re.sub(r"\D", "", value)
        return "[已脱敏电话]" if 7 <= len(digits) <= 15 else value

    redacted = _PHONE.sub(replace_phone, redacted)
    for company in sorted((name.strip() for name in company_names if name.strip()), key=len, reverse=True):
        redacted = re.sub(re.escape(company), "[已脱敏公司]", redacted, flags=re.IGNORECASE)
    return redacted


def redact_messages(
    messages: Iterable[CapturedMessage], company_names: Iterable[str] = ()
) -> list[CapturedMessage]:
    companies = list(company_names)
    return [
        replace(message, content=redact_text(message.content, companies))
        for message in messages
    ]
