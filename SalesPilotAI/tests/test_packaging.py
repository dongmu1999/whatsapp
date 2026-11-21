from __future__ import annotations

import re
import sys
from pathlib import Path

from app import config

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_packaging_files_exist():
    for relative in (
        "requirements-build.txt",
        "packaging/SalesPilotAI.spec",
        "packaging/installer.iss",
        "packaging/installer.nsi",
        "packaging/version_info.txt",
        "packaging/ChineseSimplified.isl",
        "scripts/build_windows.ps1",
        "scripts/build_windows.bat",
        "assets/salespilot.ico",
    ):
        assert (ROOT / relative).is_file(), relative


def test_versions_are_consistent_across_packaging_files():
    installer = _read(PACKAGING / "installer.iss")
    version_info = _read(PACKAGING / "version_info.txt")

    installer_version = re.search(
        r'#define MyAppVersion "([^"]+)"', installer
    )
    assert installer_version is not None
    assert installer_version.group(1) == config.APP_VERSION

    file_version = re.search(r"filevers=\((\d+), (\d+), (\d+), (\d+)\)", version_info)
    assert file_version is not None
    assert ".".join(file_version.groups()[:3]) == config.APP_VERSION
    assert f'MyAppVersionFull "{config.APP_VERSION}.0"' in installer

    assert "SalesPilotAI.exe" in installer


def test_installer_is_chinese_per_user_and_keeps_user_data():
    installer = _read(PACKAGING / "installer.iss")

    assert 'MessagesFile: "ChineseSimplified.isl"' in installer
    assert "PrivilegesRequired=lowest" in installer
    assert "ArchitecturesAllowed=x64compatible" in installer
    assert "MinVersion=10.0" in installer
    assert "{uninstallexe}" in installer
    assert "desktopicon" in installer
    assert "CloseApplications=yes" in installer
    assert "UninstallDelete" not in installer
    assert "LOCALAPPDATA" not in installer


def test_nsis_installer_is_chinese_per_user_and_keeps_user_data():
    installer = _read(PACKAGING / "installer.nsi")

    assert "Unicode true" in installer
    assert 'MUI_LANGUAGE "SimpChinese"' in installer
    assert "RequestExecutionLevel user" in installer
    assert "$LOCALAPPDATA\\Programs\\SalesPilotAI" in installer
    assert "WriteUninstaller" in installer
    assert "CreateShortCut" in installer
    assert 'RMDir /r "$INSTDIR\\_internal"' in installer
    assert "RunningX64" in installer
    assert "CheckAppRunning" in installer
    assert "tasklist.exe" in installer
    assert "%LOCALAPPDATA%\\SalesPilotAI" in installer
    assert '!define MyAppVersion "1.0.0"' in installer


def test_pyinstaller_spec_bundles_assets_and_excludes_optional_ocr():
    spec = _read(PACKAGING / "SalesPilotAI.spec")

    assert "assets" in spec
    assert "keyring.backends.Windows" in spec
    assert "mss.windows" in spec
    assert "paddleocr" in spec
    assert "excludes" in spec


def test_build_script_builds_smoke_tested_exe_and_installer():
    script = _read(ROOT / "scripts" / "build_windows.ps1")

    assert "requirements-build.txt" in script
    assert "packaging\\SalesPilotAI.spec" in script
    assert "--smoke-test" in script
    assert "ISCC.exe" in script
    assert "dist\\installer" in script
    assert "SkipInstaller" in script


def test_resource_dir_prefers_frozen_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert config.get_resource_dir() == tmp_path

    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert config.get_resource_dir() == config.PROJECT_ROOT


def test_main_smoke_mode_initializes_database(application, tmp_path, monkeypatch):
    import main

    monkeypatch.setenv("SALESPILOT_DATA_DIR", str(tmp_path))
    assert main.main(["--smoke-test"]) == 0
    assert (tmp_path / "salespilot.db").is_file()
