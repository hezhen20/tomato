@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo   Tomato Timer Builder
echo ========================================
echo.

cd /d "%~dp0"

echo [1/2] Installing PyInstaller...
python -m pip install pyinstaller -q
if errorlevel 1 (
    echo PyInstaller install failed. Check Python installation.
    pause
    exit /b 1
)

echo [2/2] Building...
python -m PyInstaller --noconfirm --onedir --windowed --name "TomatoTimer" --add-data "app/ui/style.qss;app/ui" main.py
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Build done!
echo   Output: dist\TomatoTimer\
echo   Run:    dist\TomatoTimer\TomatoTimer.exe
echo ========================================
pause
