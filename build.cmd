@echo off
chcp 65001 >nul 2>&1
title NOVA AI - Build EXE
cls

echo ============================================
echo    NOVA AI - Building Windows EXE
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    pause
    exit /b 1
)

echo [1/4] Installing build tools...
pip install pyinstaller >nul 2>&1

echo.
echo [2/4] Installing Playwright browsers...
python -m playwright install >nul 2>&1

echo.
echo [3/4] Building EXE (this takes 3-10 minutes)...
pyinstaller Nova-AI.spec --noconfirm

if errorlevel 1 (
    echo.
    echo Build FAILED. Check errors above.
    pause
    exit /b 1
)

echo.
echo [4/4] Build complete!
echo.
echo ============================================
echo    EXE location: dist\Nova-AI\Nova-AI.exe
echo ============================================
echo.
echo You can run it directly or copy the whole
echo dist\Nova-AI folder to share with others.
echo.
pause
