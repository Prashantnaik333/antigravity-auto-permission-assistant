# Antigravity Auto Permission Assistant (AAPA) - Windows Installer
# Automated, isolated setup script for Windows. Does NOT require administrator privileges.

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Antigravity Auto Permission Assistant (AAPA) Installer  " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python installation
Write-Host "[1/6] Checking Python installation..." -ForegroundColor Yellow
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    $PythonCmd = Get-Command py -ErrorAction SilentlyContinue
}

if (-not $PythonCmd) {
    Write-Host "ERROR: Python is not detected in your PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.11 or newer from https://www.python.org/downloads/." -ForegroundColor Red
    Write-Host "Make sure to check the box 'Add python.exe to PATH' during installation." -ForegroundColor Red
    Exit 1
}

$PyVersionOutput = & $PythonCmd.Source --version 2>&1
Write-Host "Found Python: $PyVersionOutput ($($PythonCmd.Source))" -ForegroundColor Green

# 2. Set repository root
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -Path $RepoRoot
Write-Host "[2/6] Working directory set to: $RepoRoot" -ForegroundColor Yellow

# 3. Create Virtual Environment
$VenvDir = Join-Path $RepoRoot ".venv"
Write-Host "[3/6] Setting up isolated Python virtual environment (.venv)..." -ForegroundColor Yellow
if (-not (Test-Path $VenvDir)) {
    & $PythonCmd.Source -m venv $VenvDir
    Write-Host "Virtual environment created at: $VenvDir" -ForegroundColor Green
} else {
    Write-Host "Existing virtual environment found at: $VenvDir" -ForegroundColor Green
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "ERROR: Virtual environment python executable not found at $VenvPython" -ForegroundColor Red
    Exit 1
}

# 4. Install / Upgrade Dependencies
Write-Host "[4/6] Installing dependencies..." -ForegroundColor Yellow
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $RepoRoot "requirements.txt")
& $VenvPython -m pip install -e $RepoRoot

# 5. Run Verification Self-Test
Write-Host "[5/6] Verifying installation with test suite..." -ForegroundColor Yellow
& $VenvPython -m pytest (Join-Path $RepoRoot "tests") -q
if ($LASTEXITCODE -eq 0) {
    Write-Host "All self-tests passed successfully!" -ForegroundColor Green
} else {
    Write-Host "Warning: Some tests reported issues, but core installation completed." -ForegroundColor Yellow
}

# 6. Create Convenient Launcher Batch File
Write-Host "[6/6] Creating desktop runner shortcut..." -ForegroundColor Yellow
$RunnerBat = Join-Path $RepoRoot "run_windows.bat"
$BatContent = @"
@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
start "" python -m aapa.main %*
"@
Set-Content -Path $RunnerBat -Value $BatContent -Encoding ASCII
Write-Host "Created launcher: $RunnerBat" -ForegroundColor Green

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  Installation Completed Successfully!                   " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "To launch the AAPA Desktop Dashboard, run:" -ForegroundColor Cyan
Write-Host "  .\run_windows.bat" -ForegroundColor White
Write-Host ""
Write-Host "Or via PowerShell:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\python -m aapa.main" -ForegroundColor White
Write-Host ""
