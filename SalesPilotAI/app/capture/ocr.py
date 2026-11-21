"""mss 临时截图与可替换 PaddleOCR 接口。"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from app.capture.errors import CaptureFailedError, CaptureUnavailableError
from app.capture.models import WindowInfo
from app.models.message import CapturedMessage, utc_now_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OCRLine:
    text: str
    confidence: float | None = None
    box: tuple[tuple[float, float], ...] | None = None


@dataclass(frozen=True)
class OCRResult:
    lines: list[OCRLine] = field(default_factory=list)


def ocr_lines_to_messages(
    result: OCRResult, recognized_at: str | None = None
) -> list[CapturedMessage]:
    recognized_at = recognized_at or utc_now_text()

    def sort_key(item):
        index, line = item
        if not line.box:
            return (float("inf"), float("inf"), index)
        return (
            min(point[1] for point in line.box),
            min(point[0] for point in line.box),
            index,
        )

    messages = []
    for _, line in sorted(enumerate(result.lines), key=sort_key):
        if not line.text.strip():
            continue
        messages.append(
            CapturedMessage(
                content=line.text.strip(),
                sender_type="unknown",
                source="ocr",
                recognized_at=recognized_at,
                confidence=line.confidence,
            )
        )
    return messages


class ScreenshotService:
    """截图写入系统临时目录，由调用方识别后立即删除。"""

    def capture_window(self, window: WindowInfo) -> Path:
        if not window.bounds:
            raise CaptureFailedError("无法确定当前窗口截图区域，请使用手动框选。")
        return self._capture(window.bounds)

    def capture_region(
        self, window: WindowInfo, bounds: tuple[int, int, int, int]
    ) -> Path:
        return self._capture(bounds)

    def _capture(self, bounds: tuple[int, int, int, int]) -> Path:
        try:
            import mss
            from mss.tools import to_png
        except ImportError as exc:
            raise CaptureUnavailableError("截图组件 mss 未安装，请安装依赖或手动粘贴。") from exc

        left, top, right, bottom = (int(value) for value in bounds)
        if right <= left or bottom <= top:
            raise ValueError("截图区域宽度和高度必须大于零")
        path = Path(tempfile.gettempdir()) / f"salespilot-capture-{uuid.uuid4().hex}.png"
        try:
            with mss.mss() as capture:
                image = capture.grab(
                    {"left": left, "top": top, "width": right - left, "height": bottom - top}
                )
                to_png(image.rgb, image.size, output=str(path))
        except Exception as exc:
            self.cleanup(path)
            logger.exception("mss 截图失败")
            raise CaptureFailedError("截图失败，请检查窗口区域或改用手动粘贴。") from exc
        return path

    @staticmethod
    def cleanup(path: str | Path) -> None:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            logger.warning("临时截图清理失败：%s", path, exc_info=True)


class PaddleOCREngine:
    """延迟加载 PaddleOCR；未安装时不影响手动捕获和程序启动。"""

    def __init__(self, language: str = "ch"):
        self.language = language
        self._engine = None

    def recognize(self, image_path: str | Path) -> OCRResult:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise CaptureUnavailableError(
                "OCR 组件未安装。可安装 PaddleOCR 与 PaddlePaddle，或直接使用手动粘贴。"
            ) from exc
        try:
            if self._engine is None:
                self._engine = PaddleOCR(use_angle_cls=True, lang=self.language)
            raw_result = self._engine.ocr(str(image_path), cls=True)
            return OCRResult(self._extract_lines(raw_result))
        except Exception as exc:
            logger.exception("PaddleOCR 识别失败")
            raise CaptureFailedError("OCR 识别失败，请编辑截图区域或改用手动粘贴。") from exc

    @classmethod
    def _extract_lines(cls, value) -> list[OCRLine]:
        lines: list[OCRLine] = []
        if isinstance(value, (list, tuple)):
            if (
                len(value) == 2
                and isinstance(value[1], (list, tuple))
                and len(value[1]) >= 2
                and isinstance(value[1][0], str)
            ):
                box = value[0]
                normalized_box = None
                if isinstance(box, (list, tuple)):
                    try:
                        normalized_box = tuple(
                            (float(point[0]), float(point[1])) for point in box
                        )
                    except (TypeError, ValueError, IndexError):
                        normalized_box = None
                confidence = None
                try:
                    confidence = float(value[1][1])
                except (TypeError, ValueError):
                    pass
                lines.append(OCRLine(value[1][0], confidence, normalized_box))
                return lines
            for item in value:
                lines.extend(cls._extract_lines(item))
        return lines
