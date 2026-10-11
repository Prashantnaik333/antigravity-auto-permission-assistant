# Installation & Deployment Guide

This guide covers setting up **Antigravity Auto Permission Assistant (AAPA)** on Windows, Linux, and macOS.

---

## 1. System Requirements

- **Operating System**: Windows 10/11 (Primary), Linux (Ubuntu 20.04+, Fedora 38+), or macOS (12+)
- **Python**: Version 3.11 or newer
- **Privileges**: Standard user privileges (Administrator / Root is **NOT** required)
- **Disk Space**: ~150 MB (including Python virtual environment and PySide6 Qt libraries)

---

## 2. Beginner-Friendly Windows Quick Install

### Method A: Automated PowerShell Installation (Recommended)

1. Clone or download the repository:
   ```powershell
   git clone https://github.com/google-antigravity/antigravity-auto-permission-assistant.git
   cd antigravity-auto-permission-assistant
   ```

2. Run the Windows installation script:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
   ```

3. Launch the desktop application:
   ```cmd
   run_windows.bat
   ```

The script will automatically:
- Verify Python 3.11+
- Create an isolated `.venv` directory
- Install dependencies without affecting global Python
- Run the test suite to verify system integrity
- Create a `run_windows.bat` shortcut

---

## 3. Manual Virtual Environment Installation

If you prefer to configure the environment manually:

### Windows (PowerShell or Command Prompt):
```cmd
# 1. Create virtual environment
python -m venv .venv

# 2. Activate virtual environment
.venv\Scripts\activate

# 3. Upgrade pip and install package
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# 4. Verify test suite
pytest

# 5. Launch Application
python -m aapa.main
```

### Linux / macOS:
```bash
# 1. Run automated installer
chmod +x scripts/install_linux.sh
./scripts/install_linux.sh

# 2. Launch Application
./run_linux.sh
```

---

## 4. Standalone Windows Executable Build (PyInstaller)

If you wish to distribute AAPA as a self-contained `.exe` that does not require Python on the target machine:

1. Ensure the virtual environment is activated:
   ```powershell
   .\.venv\Scripts\activate
   ```

2. Run the build script:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
   ```

3. The compiled binary will be placed in:
   ```
   dist\AAPA\AAPA.exe
   ```

---

## 5. Uninstallation & Clean Removal

AAPA stores settings in standard user directories without modifying Windows registry keys or system paths.

To completely uninstall AAPA:

1. Open AAPA and navigate to **Settings & Integration**, then click **Uninstall Hooks**. (Alternatively, run `python -m aapa.main --uninstall-hooks`).
2. Delete the application data directory:
   - **Windows**: `%LOCALAPPDATA%\aapa` (or `C:\Users\<username>\AppData\Local\aapa`)
   - **Linux/macOS**: `~/.config/aapa`
3. Delete the repository folder or standalone executable.
