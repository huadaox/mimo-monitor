@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo   Mimo Monitor - Windows Tray Build
echo ========================================
echo.

echo [*] Building...
echo.

python -m PyInstaller --onefile --windowed --name "MimoMonitor" tray_windows.py

echo.
if exist "dist\MimoMonitor.exe" (
    echo [+] Build success!
    echo     Output: dist\MimoMonitor.exe
) else (
    echo [-] Build failed
)

pause
