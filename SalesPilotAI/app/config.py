"""应用路径与基础配置。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "SalesPilot AI"
APP_NAME_ZH = "WhatsApp 外贸销售智能助手"
APP_VERSION = "1.0.0"
ORGANIZATION_NAME = "SalesPilot"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_resource_dir() -> Path:
    """返回源码或 PyInstaller 打包后的只读资源根目录。"""
    if getattr(sys, "frozen", False):
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            return Path(bundle_dir)
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


ASSETS_DIR = get_resource_dir() / "assets"


def get_data_dir() -> Path:
    """返回可写的本地数据目录；环境变量主要用于开发和自动化测试。"""
    if override := os.environ.get("SALESPILOT_DATA_DIR"):
        return Path(override).expanduser().resolve()

    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "SalesPilotAI"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "SalesPilotAI"

    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "SalesPilotAI"


def get_database_path() -> Path:
    return get_data_dir() / "salespilot.db"


def ensure_data_dir() -> Path:
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
