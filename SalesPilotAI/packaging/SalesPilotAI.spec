# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir 打包配置，输出 dist/SalesPilotAI/SalesPilotAI.exe。"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
ASSETS = ROOT / "assets"
PACKAGING = ROOT / "packaging"

hidden_imports = []
if sys.platform == "win32":
    hidden_imports += [
        "keyring.backends.Windows",
        "mss.windows",
        "pywinauto.backend",
        "pywinauto.controls.uiawrapper",
    ]
else:
    hidden_imports += ["keyring.backends.SecretService", "mss.linux"]

excludes = [
    "paddle",
    "paddlepaddle",
    "paddleocr",
    "torch",
    "torchvision",
    "pytest",
    "tkinter",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "IPython",
    "notebook",
]

icon_path = ASSETS / "salespilot.ico"
icon = str(icon_path) if sys.platform == "win32" and icon_path.is_file() else None
version = (
    str(PACKAGING / "version_info.txt") if sys.platform == "win32" else None
)

analysis = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ASSETS), "assets")],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="SalesPilotAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
    version=version,
)

collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SalesPilotAI",
)
