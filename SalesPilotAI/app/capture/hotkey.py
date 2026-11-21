"""Windows RegisterHotKey 全局快捷键；仅通知用户触发，不监听聊天。"""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from app.capture.errors import CaptureUnavailableError

logger = logging.getLogger(__name__)
_MODIFIERS = {"ctrl": 0x0002, "control": 0x0002, "shift": 0x0004, "alt": 0x0001, "win": 0x0008}


@dataclass(frozen=True)
class HotkeyBinding:
    normalized: str
    modifiers: int
    virtual_key: int


def parse_hotkey(sequence: str) -> HotkeyBinding:
    parts = [part.strip() for part in str(sequence).split("+") if part.strip()]
    if len(parts) < 2:
        raise ValueError("快捷键必须包含修饰键和一个主键，例如 Ctrl+Shift+A")
    *modifier_names, key_name = parts
    modifiers = 0
    seen = set()
    for name in modifier_names:
        folded = name.casefold()
        canonical = "ctrl" if folded == "control" else folded
        if folded not in _MODIFIERS or canonical in seen:
            raise ValueError("快捷键包含无效或重复的修饰键")
        seen.add(canonical)
        modifiers |= _MODIFIERS[folded]
    key = key_name.upper()
    if len(key) == 1 and (key.isascii() and key.isalnum()):
        virtual_key = ord(key)
    elif key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        virtual_key = 0x70 + int(key[1:]) - 1
    else:
        raise ValueError("快捷键主键仅支持字母、数字或 F1—F24")
    names = []
    for display, folded in (("Ctrl", "ctrl"), ("Shift", "shift"), ("Alt", "alt"), ("Win", "win")):
        if folded in seen:
            names.append(display)
    normalized = "+".join([*names, key])
    return HotkeyBinding(normalized, modifiers, virtual_key)


class GlobalHotkeyManager(QObject):
    triggered = Signal(str)
    error = Signal(str)
    ready = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._thread_id = None
        self._binding: HotkeyBinding | None = None

    def start(self, sequence: str = "Ctrl+Shift+A") -> None:
        binding = parse_hotkey(sequence)
        if sys.platform != "win32":
            raise CaptureUnavailableError("全局快捷键仅支持 Windows；页面捕获按钮仍可使用。")
        self.stop()
        self._binding = binding
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, args=(binding,), name="SalesPilotHotkey", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive() and self._thread_id:
            try:
                ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
            except Exception:
                logger.debug("通知快捷键线程退出失败", exc_info=True)
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
        self._thread = None
        self._thread_id = None

    def _run(self, binding: HotkeyBinding) -> None:
        from ctypes import wintypes

        class MSG(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM),
                ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD),
                ("pt_x", wintypes.LONG),
                ("pt_y", wintypes.LONG),
            ]

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._thread_id = user32.GetCurrentThreadId()
        registered = False
        try:
            registered = bool(
                user32.RegisterHotKey(None, 1, binding.modifiers | 0x4000, binding.virtual_key)
            )
            if not registered:
                self.error.emit("全局快捷键注册失败，可能被其他程序占用，请修改快捷键。")
                return
            self.ready.emit(binding.normalized)
            message = MSG()
            while not self._stop_event.is_set():
                result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result <= 0:
                    break
                if message.message == 0x0312 and message.wParam == 1:
                    self.triggered.emit(binding.normalized)
        except Exception:
            logger.exception("全局快捷键监听异常")
            self.error.emit("全局快捷键运行异常，请重新保存快捷键或改用页面按钮。")
        finally:
            if registered:
                user32.UnregisterHotKey(None, 1)
