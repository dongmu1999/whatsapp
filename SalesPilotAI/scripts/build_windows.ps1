# Build SalesPilot AI on Windows: tests -> PyInstaller EXE -> smoke test -> Inno Setup installer.
[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$SkipTests,
    [switch]$SkipInstaller,
    [switch]$ReuseVenv
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if ([System.Environment]::OSVersion.Platform -ne "Win32NT") {
    throw "This script must run on Windows 10/11."
}

$Venv = Join-Path $Root ".venv-build"
$VenvPython = Join-Path $Venv "Scripts\python.exe"

if (-not $ReuseVenv -or -not (Test-Path $VenvPython)) {
    Write-Host "[1/5] Creating build virtual environment..."
    & $Python -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "Failed to create the build virtual environment." }
}

Write-Host "[2/5] Installing runtime and build dependencies..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip." }
& $VenvPython -m pip install -r requirements.txt -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Failed to install dependencies." }

if (-not $SkipTests) {
    Write-Host "[3/5] Running automated tests..."
    & $VenvPython -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Tests failed; packaging stopped." }
} else {
    Write-Host "[3/5] Tests skipped by request."
}

Write-Host "[4/5] Building EXE with PyInstaller..."
& $VenvPython -m PyInstaller --noconfirm --clean packaging\SalesPilotAI.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$Exe = Join-Path $Root "dist\SalesPilotAI\SalesPilotAI.exe"
if (-not (Test-Path $Exe)) { throw "Missing packaged executable: $Exe" }

$SmokeDir = Join-Path ([System.IO.Path]::GetTempPath()) ("SalesPilotAI-smoke-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $SmokeDir | Out-Null
$PreviousDataDir = $env:SALESPILOT_DATA_DIR
try {
    $env:SALESPILOT_DATA_DIR = $SmokeDir
    $Process = Start-Process -FilePath $Exe -ArgumentList "--smoke-test" -PassThru -Wait
    if ($Process.ExitCode -ne 0) {
        throw "Packaged EXE smoke test failed with exit code $($Process.ExitCode)."
    }
    if (-not (Test-Path (Join-Path $SmokeDir "salespilot.db"))) {
        throw "Packaged EXE did not initialize the local database."
    }
    Write-Host "Packaged EXE smoke test passed and initialized salespilot.db."
} finally {
    $env:SALESPILOT_DATA_DIR = $PreviousDataDir
    Remove-Item -Recurse -Force $SmokeDir -ErrorAction SilentlyContinue
}

if ($SkipInstaller) {
    Write-Host "Installer skipped by request. EXE: $Exe"
    exit 0
}

Write-Host "[5/5] Building installer with Inno Setup..."
$IsccCommand = Get-Command iscc.exe -ErrorAction SilentlyContinue
$Iscc = if ($IsccCommand) { $IsccCommand.Source } else { $null }
if (-not $Iscc) {
    $Candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $Iscc = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $Iscc) {
    throw "Inno Setup 6.5+ ISCC.exe not found. Install it or rerun with -SkipInstaller."
}

$Version = (& $VenvPython -c "from app.config import APP_VERSION; print(APP_VERSION)").Trim()
$InstallerDir = Join-Path $Root "dist\installer"
New-Item -ItemType Directory -Force -Path $InstallerDir | Out-Null
& $Iscc "/DMyAppVersion=$Version" "/DSourceDir=$Root\dist\SalesPilotAI" "/DOutputDir=$InstallerDir" "packaging\installer.iss"
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed." }

$Setup = Join-Path $InstallerDir "SalesPilotAI-Setup-$Version.exe"
if (-not (Test-Path $Setup)) { throw "Missing installer: $Setup" }

Write-Host "Build complete."
Write-Host "EXE:       $Exe"
Write-Host "Installer: $Setup"
