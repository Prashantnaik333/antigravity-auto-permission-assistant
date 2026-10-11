# Antigravity Auto Permission Assistant (AAPA) - Standalone Executable Builder
# Packages the PySide6 application into a standalone Windows binary using PyInstaller.

[CmdletBinding()]
param(
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  AAPA Standalone Executable Build Script (PyInstaller)   " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -Path $RepoRoot

$PythonCmd = if (Test-Path "$RepoRoot\.venv\Scripts\python.exe") {
    "$RepoRoot\.venv\Scripts\python.exe"
} else {
    (Get-Command python).Source
}

Write-Host "Using Python: $PythonCmd" -ForegroundColor Yellow

# Ensure PyInstaller is installed
Write-Host "Checking PyInstaller..." -ForegroundColor Yellow
& $PythonCmd -m pip install --upgrade pyinstaller

$BuildMode = if ($OneFile) { "--onefile" } else { "--onedir" }

Write-Host "Building application with PyInstaller ($BuildMode)..." -ForegroundColor Yellow
& $PythonCmd -m PyInstaller `
    $BuildMode `
    --windowed `
    --name "AAPA" `
    --add-data "config/default_policy.json;config" `
    --add-data "config/settings.example.json;config" `
    --clean `
    --noconfirm `
    "src/aapa/main.py"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Build Succeeded!" -ForegroundColor Green
    Write-Host "Executable generated in: $RepoRoot\dist\AAPA\" -ForegroundColor Cyan
} else {
    Write-Host "Build failed with exit code $LASTEXITCODE" -ForegroundColor Red
}
