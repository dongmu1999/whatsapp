"""Windows 前台窗口识别与 UI Automation 只读适配。"""

from __future__ import annotations

import logging
import sys

from app.capture.errors import CaptureFailedError, CaptureUnavailableError
from app.capture.models import UIAReadResult, WindowInfo
from app.models.message import MessageParser

logger = logging.getLogger(__name__)
_BROWSER_MARKERS = (
    "chrome",
    "msedge",
    "firefox",
    "brave",
    "opera",
    "chromium",
    "microsoft edge",
)


def is_whatsapp_window(window: WindowInfo, allow_browser: bool = False) -> bool:
    title = window.title.casefold()
    process = window.process_name.casefold()
    class_name = window.class_name.casefold()
    combined = f"{title} {process} {class_name}"
    if "whatsapp" not in combined:
        return False
    is_browser = any(marker in f"{title} {process}" for marker in _BROWSER_MARKERS)
    return allow_browser or not is_browser


class WindowsWindowDetector:
    def get_foreground_window(self) -> WindowInfo:
        if sys.platform != "win32":
            raise CaptureUnavailableError(
                "前台窗口识别仅支持 Windows；当前环境请使用手动粘贴或导入截图。"
            )
        try:
            from pywinauto import Desktop
            from pywinauto.application import process_get_module_name

            active = Desktop(backend="uia").get_active()
            process_name = ""
            try:
                process_name = process_get_module_name(active.element_info.process_id)
            except Exception:
                logger.debug("无法读取前台进程名称", exc_info=True)
            rectangle = active.rectangle()
            return WindowInfo(
                title=active.window_text() or "",
                process_name=process_name or "",
                class_name=active.element_info.class_name or "",
                handle=active.handle,
                bounds=(rectangle.left, rectangle.top, rectangle.right, rectangle.bottom),
            )
        except CaptureUnavailableError:
            raise
        except Exception as exc:
            logger.exception("读取 Windows 前台窗口失败")
            raise CaptureUnavailableError(
                "无法识别前台窗口，请确认已安装 Windows 捕获组件，或改用手动粘贴。"
            ) from exc


class WindowsUIAReader:
    """只读取当前可见且系统允许访问的 UIA 文本，不点击或发送任何内容。"""

    def read(self, window: WindowInfo) -> UIAReadResult:
        if sys.platform != "win32":
            raise CaptureUnavailableError("UI Automation 仅支持 Windows。")
        try:
            from pywinauto import Desktop

            desktop = Desktop(backend="uia")
            target = (
                desktop.window(handle=window.handle)
                if window.handle is not None
                else desktop.get_active()
            )
            texts: list[str] = []
            chat_title = ""
            chat_region = window.bounds
            for element in target.descendants():
                try:
                    text = (element.window_text() or "").strip()
                    info = element.element_info
                    automation_id = str(getattr(info, "automation_id", "") or "")
                    control_type = str(getattr(info, "control_type", "") or "")
                    folded_id = automation_id.casefold()
                    if not chat_title and text and any(
                        marker in folded_id for marker in ("conversationtitle", "chattitle")
                    ):
                        chat_title = text
                    if (
                        chat_region == window.bounds
                        and control_type == "List"
                        and any(marker in folded_id for marker in ("message", "chat", "conversation"))
                    ):
                        rectangle = element.rectangle()
                        chat_region = (
                            rectangle.left,
                            rectangle.top,
                            rectangle.right,
                            rectangle.bottom,
                        )
                    if text and control_type in {"Text", "Edit", "ListItem"}:
                        texts.append(text)
                except Exception:
                    logger.debug("跳过不可读取的 UIA 元素", exc_info=True)
            messages = MessageParser.parse("\n".join(texts), source="uia")
            return UIAReadResult(
                chat_title=chat_title or window.title,
                messages=messages,
                chat_region=chat_region,
            )
        except Exception as exc:
            logger.exception("UI Automation 读取失败")
            raise CaptureFailedError(
                "UI Automation 未能读取当前可见聊天，请尝试 OCR 或手动粘贴。"
            ) from exc
