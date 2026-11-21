"""用户主动触发的窗口检测、UIA 优先和 OCR 降级编排。"""

from __future__ import annotations

import logging
from pathlib import Path

from app.capture.errors import (
    CaptureError,
    CaptureFailedError,
    CaptureUnavailableError,
    WindowNotWhatsAppError,
)
from app.capture.models import CaptureResult, UIAReadResult, WindowInfo
from app.capture.ocr import (
    OCRResult,
    PaddleOCREngine,
    ScreenshotService,
    ocr_lines_to_messages,
)
from app.capture.windows import WindowsUIAReader, WindowsWindowDetector, is_whatsapp_window
from app.models.message import prepare_messages

logger = logging.getLogger(__name__)
_VISIBLE_WARNING = "仅包含本次主动捕获的可见内容，可能不完整，不代表完整聊天历史。"


class ChatCaptureService:
    def __init__(self, window_detector=None, uia_reader=None, screenshot_service=None, ocr_engine=None):
        self.window_detector = window_detector or WindowsWindowDetector()
        self.uia_reader = uia_reader or WindowsUIAReader()
        self.screenshot_service = screenshot_service or ScreenshotService()
        self.ocr_engine = ocr_engine or PaddleOCREngine()

    def get_target_window(self, allow_browser: bool = False) -> WindowInfo:
        window = self.window_detector.get_foreground_window()
        if not is_whatsapp_window(window, allow_browser=allow_browser):
            raise WindowNotWhatsAppError(
                "前台窗口不是 WhatsApp。请先切换到 WhatsApp Desktop / Business；"
                "WhatsApp Web 需在设置中允许。"
            )
        return window

    def capture_current(
        self,
        *,
        use_uia: bool = True,
        use_ocr: bool = True,
        allow_browser: bool = False,
        limit: int = 30,
    ) -> CaptureResult:
        window = self.get_target_window(allow_browser=allow_browser)
        errors = []
        if use_uia:
            try:
                reading = self.uia_reader.read(window)
                messages = prepare_messages(reading.messages, limit=limit)
                if messages:
                    return CaptureResult(
                        title=reading.chat_title or window.title,
                        window_title=window.title,
                        source="uia",
                        messages=messages,
                        may_be_incomplete=True,
                        warning=_VISIBLE_WARNING,
                    )
            except Exception as exc:
                logger.warning("UIA 捕获不可用，将尝试 OCR：%s", exc)
                errors.append(str(exc))
        if use_ocr:
            try:
                return self.capture_window_ocr(window, limit=limit)
            except Exception as exc:
                logger.warning("OCR 捕获不可用：%s", exc)
                errors.append(str(exc))
        detail = f"最后错误：{errors[-1]}\n" if errors else ""
        raise CaptureFailedError(
            f"{detail}未能获取可见聊天。请重新获取、调整捕获设置，或使用手动粘贴。"
        )

    def capture_window_ocr(
        self,
        window: WindowInfo,
        *,
        bounds: tuple[int, int, int, int] | None = None,
        limit: int = 30,
    ) -> CaptureResult:
        image_path = None
        try:
            if bounds is None:
                image_path = self.screenshot_service.capture_window(window)
            else:
                image_path = self.screenshot_service.capture_region(window, bounds)
            ocr_result = self.ocr_engine.recognize(image_path)
            messages = prepare_messages(ocr_lines_to_messages(ocr_result), limit=limit)
            if not messages:
                raise CaptureFailedError("截图中未识别到文字，请重新框选或手动粘贴。")
            return CaptureResult(
                title=window.title,
                window_title=window.title,
                source="ocr",
                messages=messages,
                may_be_incomplete=True,
                warning=f"{_VISIBLE_WARNING} OCR 发送方默认标记为未知，请在预览中确认。",
            )
        finally:
            if image_path is not None:
                self.screenshot_service.cleanup(image_path)

    def recognize_image(self, image_path: str | Path, *, limit: int = 30) -> CaptureResult:
        path = Path(image_path)
        if not path.is_file():
            raise CaptureFailedError("截图文件不存在，请重新选择。")
        if path.suffix.casefold() not in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
            raise CaptureFailedError("仅支持 PNG、JPG、BMP 或 WebP 截图。")
        result = self.ocr_engine.recognize(path)
        messages = prepare_messages(ocr_lines_to_messages(result), limit=limit)
        if not messages:
            raise CaptureFailedError("截图中未识别到文字，请重新选择或手动粘贴。")
        return CaptureResult(
            title=path.stem,
            window_title="手动导入截图",
            source="ocr",
            messages=messages,
            may_be_incomplete=True,
            warning=f"{_VISIBLE_WARNING} 请核对 OCR 文本和发送方。",
        )


__all__ = [
    "CaptureError",
    "CaptureFailedError",
    "CaptureUnavailableError",
    "WindowNotWhatsAppError",
    "ChatCaptureService",
]
