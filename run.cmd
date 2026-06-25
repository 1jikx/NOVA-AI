@echo off
chcp 65001 >nul 2>&1
title NOVA AI
cls

cd /d "%~dp0"

if exist "venv\Scripts\python.exe" (
    echo Starting NOVA AI...
    "venv\Scripts\python.exe" "Nova-AI-Windows.py"
    goto :done
)

if exist "venvnano\Scripts\python.exe" (
    echo Starting NOVA AI...
    "venvnano\Scripts\python.exe" "Nova-AI-Windows.py"
    goto :done
)

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo Install Python 3.11/3.12 from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH"
    pause
    exit /b 1
)

echo Starting NOVA AI with system Python...
python "Nova-AI-Windows.py"

:done
pause
