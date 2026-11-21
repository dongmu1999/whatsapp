"""浅色与深色主题加载。"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from app.config import ASSETS_DIR

LIGHT_THEME = "light"
DARK_THEME = "dark"
VALID_THEMES = {LIGHT_THEME, DARK_THEME}


def apply_theme(application: QApplication, theme: str) -> None:
    if theme not in VALID_THEMES:
        raise ValueError(f"不支持的主题：{theme}")

    style_file = ASSETS_DIR / "styles" / f"{theme}.qss"
    application.setStyleSheet(style_file.read_text(encoding="utf-8"))
    application.setProperty("theme", theme)
