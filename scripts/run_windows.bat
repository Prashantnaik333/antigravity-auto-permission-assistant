@echo off
setlocal
cd /d "%~dp0\.."

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo Starting Antigravity Auto Permission Assistant (AAPA)...
"%PYTHON_EXE%" -m aapa.main %*
endlocal
