from __future__ import annotations

from pathlib import Path

import pytest

from app.capture.hotkey import GlobalHotkeyManager, parse_hotkey
from app.capture.models import CaptureResult, UIAReadResult, WindowInfo
from app.capture.ocr import OCRLine, OCRResult, ocr_lines_to_messages
from app.capture.windows import WindowsWindowDetector, is_whatsapp_window
from app.models.message import CapturedMessage, MessageParser, prepare_messages
from app.services.chat_capture_service import (
    CaptureFailedError,
    CaptureUnavailableError,
    ChatCaptureService,
    WindowNotWhatsAppError,
)


RECOGNIZED_AT = "2026-11-21T08:00:00Z"


def test_parser_supports_whatsapp_export_multiline_and_sender_names():
    text = (
        "11/21/26, 10:30 - Alice: Hello, need 500 units\n"
        "Please quote your best price.\n"
        "11/21/26, 10:31 - Me: Sure, I will check.\n"
    )

    messages = MessageParser.parse(
        text, customer_name="Alice", sales_name="Me", recognized_at=RECOGNIZED_AT
    )

    assert len(messages) == 2
    assert messages[0].content == "Hello, need 500 units\nPlease quote your best price."
    assert messages[0].timestamp == "11/21/26, 10:30"
    assert messages[0].sender_type == "customer"
    assert messages[0].sender_name == "Alice"
    assert messages[1].sender_type == "sales"
    assert all(message.source == "manual" for message in messages)
    assert all(message.recognized_at == RECOGNIZED_AT for message in messages)


def test_parser_preserves_unknown_sender_and_original_english():
    messages = MessageParser.parse(
        "[2026-11-21, 10:30:00] Unknown Person:  Keep MY original Price & MOQ",
        recognized_at=RECOGNIZED_AT,
    )

    assert len(messages) == 1
    assert messages[0].sender_type == "unknown"
    assert messages[0].content == "Keep MY original Price & MOQ"


def test_parser_supports_explicit_chinese_sender_labels():
    messages = MessageParser.parse(
        "客户：请报价\n销售：好的\n普通可见文本", recognized_at=RECOGNIZED_AT
    )

    assert [message.sender_type for message in messages] == [
        "customer",
        "sales",
        "unknown",
    ]
    assert messages[-1].content == "普通可见文本"


def test_prepare_messages_removes_only_adjacent_duplicates_and_keeps_recent_order():
    messages = [
        CapturedMessage("Hello", timestamp="10:00"),
        CapturedMessage("Hello", timestamp="10:00"),
        CapturedMessage("Price?", timestamp="10:01"),
        CapturedMessage("Hello", timestamp="10:02"),
    ]

    prepared = prepare_messages(messages, limit=3)

    assert [message.content for message in prepared] == ["Hello", "Price?", "Hello"]
    assert [message.content for message in prepare_messages(messages, limit=2)] == [
        "Price?",
        "Hello",
    ]
    with pytest.raises(ValueError, match="消息数量"):
        prepare_messages(messages, limit=0)


def test_message_rejects_empty_content_invalid_sender_and_confidence():
    with pytest.raises(ValueError, match="消息内容"):
        CapturedMessage("  ")
    with pytest.raises(ValueError, match="发送方"):
        CapturedMessage("Hello", sender_type="robot")
    with pytest.raises(ValueError, match="置信度"):
        CapturedMessage("Hello", confidence=1.1)


def test_window_detection_supports_desktop_and_optional_browser_targets():
    desktop = WindowInfo("Alice - WhatsApp", process_name="WhatsApp.exe")
    browser = WindowInfo("WhatsApp - Google Chrome", process_name="chrome.exe")
    other = WindowInfo("Quarterly report - Word", process_name="WINWORD.EXE")

    assert is_whatsapp_window(desktop)
    assert not is_whatsapp_window(browser)
    assert is_whatsapp_window(browser, allow_browser=True)
    assert not is_whatsapp_window(other, allow_browser=True)


def test_windows_detector_reports_unsupported_platform(monkeypatch):
    monkeypatch.setattr("app.capture.windows.sys.platform", "linux")
    with pytest.raises(CaptureUnavailableError, match="Windows"):
        WindowsWindowDetector().get_foreground_window()


class FakeDetector:
    def __init__(self, window):
        self.window = window

    def get_foreground_window(self):
        return self.window


class FakeUIA:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def read(self, window):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


class FakeScreenshot:
    def __init__(self, path):
        self.path = path
        self.cleaned = []

    def capture_window(self, window):
        return self.path

    def capture_region(self, window, bounds):
        return self.path

    def cleanup(self, path):
        self.cleaned.append(path)


class FakeOCR:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def recognize(self, image_path):
        self.calls.append(image_path)
        return self.result


def _uia_result(*contents):
    return UIAReadResult(
        chat_title="Alice",
        messages=[
            CapturedMessage(content, source="uia", recognized_at=RECOGNIZED_AT)
            for content in contents
        ],
        chat_region=(10, 20, 800, 600),
    )


def test_capture_prefers_uia_and_does_not_invoke_ocr(tmp_path):
    window = WindowInfo("WhatsApp", process_name="WhatsApp.exe")
    uia = FakeUIA(_uia_result("First", "Second"))
    screenshot = FakeScreenshot(tmp_path / "unused.png")
    ocr = FakeOCR(OCRResult([]))
    service = ChatCaptureService(FakeDetector(window), uia, screenshot, ocr)

    result = service.capture_current(limit=30)

    assert isinstance(result, CaptureResult)
    assert result.title == "Alice"
    assert result.source == "uia"
    assert result.may_be_incomplete
    assert [message.content for message in result.messages] == ["First", "Second"]
    assert uia.calls == 1
    assert ocr.calls == []
    assert screenshot.cleaned == []


def test_capture_falls_back_to_ocr_and_cleans_temporary_screenshot(tmp_path):
    window = WindowInfo("WhatsApp", process_name="WhatsApp.exe")
    image = tmp_path / "capture.png"
    image.write_bytes(b"not-a-real-image")
    uia = FakeUIA(error=RuntimeError("UIA unavailable"))
    screenshot = FakeScreenshot(image)
    ocr = FakeOCR(
        OCRResult([OCRLine("Visible message", confidence=0.88, box=((0, 0), (1, 0), (1, 1), (0, 1)))])
    )
    service = ChatCaptureService(FakeDetector(window), uia, screenshot, ocr)

    result = service.capture_current(limit=30)

    assert result.source == "ocr"
    assert result.messages[0].content == "Visible message"
    assert result.messages[0].confidence == pytest.approx(0.88)
    assert result.messages[0].sender_type == "unknown"
    assert ocr.calls == [image]
    assert screenshot.cleaned == [image]


def test_capture_failure_mentions_manual_fallback(tmp_path):
    window = WindowInfo("WhatsApp", process_name="WhatsApp.exe")
    screenshot = FakeScreenshot(tmp_path / "empty.png")
    service = ChatCaptureService(
        FakeDetector(window),
        FakeUIA(_uia_result()),
        screenshot,
        FakeOCR(OCRResult([])),
    )

    with pytest.raises(CaptureFailedError, match="手动粘贴"):
        service.capture_current()


def test_capture_rejects_non_whatsapp_before_reading(tmp_path):
    uia = FakeUIA(_uia_result("Should not be read"))
    service = ChatCaptureService(
        FakeDetector(WindowInfo("Notepad", process_name="notepad.exe")),
        uia,
        FakeScreenshot(tmp_path / "none.png"),
        FakeOCR(OCRResult([])),
    )

    with pytest.raises(WindowNotWhatsAppError, match="切换"):
        service.capture_current()
    assert uia.calls == 0


def test_ocr_lines_are_sorted_and_never_guess_sender():
    result = OCRResult(
        [
            OCRLine("Second", 0.7, ((0, 100), (10, 100), (10, 110), (0, 110))),
            OCRLine("First", 0.9, ((0, 10), (10, 10), (10, 20), (0, 20))),
        ]
    )

    messages = ocr_lines_to_messages(result, recognized_at=RECOGNIZED_AT)

    assert [message.content for message in messages] == ["First", "Second"]
    assert all(message.sender_type == "unknown" for message in messages)
    assert all(message.source == "ocr" for message in messages)


def test_recognize_imported_image_does_not_delete_user_file(tmp_path):
    image = tmp_path / "user-screenshot.png"
    image.write_bytes(b"user owned")
    screenshot = FakeScreenshot(tmp_path / "unused.png")
    ocr = FakeOCR(OCRResult([OCRLine("Imported text", 0.8)]))
    service = ChatCaptureService(
        FakeDetector(WindowInfo("WhatsApp")), FakeUIA(), screenshot, ocr
    )

    result = service.recognize_image(image)

    assert result.title == "user-screenshot"
    assert result.messages[0].content == "Imported text"
    assert image.exists()
    assert screenshot.cleaned == []


def test_hotkey_parser_validates_default_and_rejects_invalid_sequences():
    default = parse_hotkey("Ctrl+Shift+A")
    assert default.virtual_key == ord("A")
    assert default.modifiers == 0x0002 | 0x0004
    assert default.normalized == "Ctrl+Shift+A"

    with pytest.raises(ValueError, match="快捷键"):
        parse_hotkey("Ctrl+Shift")
    with pytest.raises(ValueError, match="快捷键"):
        parse_hotkey("Ctrl+A+B")


def test_hotkey_parser_normalizes_control_alias_and_rejects_duplicate_modifier():
    binding = parse_hotkey("Control+Shift+F5")
    assert binding.normalized == "Ctrl+Shift+F5"
    assert binding.modifiers == 0x0002 | 0x0004
    with pytest.raises(ValueError, match="重复"):
        parse_hotkey("Ctrl+Control+A")


def test_global_hotkey_manager_requires_windows(monkeypatch):
    monkeypatch.setattr("app.capture.hotkey.sys.platform", "linux")
    manager = GlobalHotkeyManager()
    with pytest.raises(CaptureUnavailableError, match="Windows"):
        manager.start("Ctrl+Shift+A")
