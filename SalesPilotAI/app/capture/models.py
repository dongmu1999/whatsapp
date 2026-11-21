"""窗口与捕获结果的数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.message import CapturedMessage


@dataclass(frozen=True)
class WindowInfo:
    title: str
    process_name: str = ""
    class_name: str = ""
    handle: object | None = None
    bounds: tuple[int, int, int, int] | None = None


@dataclass(frozen=True)
class UIAReadResult:
    chat_title: str
    messages: list[CapturedMessage] = field(default_factory=list)
    chat_region: tuple[int, int, int, int] | None = None


@dataclass(frozen=True)
class CaptureResult:
    title: str
    window_title: str
    source: str
    messages: list[CapturedMessage]
    may_be_incomplete: bool = True
    warning: str = ""
