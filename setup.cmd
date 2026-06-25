@echo off
chcp 65001 >nul 2>&1
title NOVA AI - Setup
cls

echo ============================================
echo    NOVA AI - First Time Setup
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo.
    echo Install Python 3.11 or 3.12 from:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during install!
    echo Then run this script again.
    pause
    exit /b 1
)

python --version
echo.

echo [1/4] Creating virtual environment...
if exist "venv" (
    echo       Already exists, skipping.
) else (
    python -m venv venv
)

echo.
echo [2/4] Activating and upgrading pip...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip

echo.
echo [3/4] Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo [4/4] Installing Playwright browsers...
python -m playwright install

echo.
echo ============================================
echo    Setup complete!
echo ============================================
echo.
echo To run NOVA: double-click run.cmd
echo To build EXE: double-click build.cmd
echo.
pause
