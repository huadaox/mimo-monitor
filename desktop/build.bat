@echo off
REM Mimo Monitor - Windows 托盘打包脚本
REM 需要先安装 pyinstaller: pip install pyinstaller

echo ========================================
echo   Mimo Monitor - Windows 托盘打包
echo ========================================
echo.

REM 检查依赖
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [!] 未安装 pyinstaller，正在安装...
    pip install pyinstaller
)

pip show pystray >nul 2>&1
if errorlevel 1 (
    echo [!] 未安装 pystray，正在安装...
    pip install pystray Pillow requests
)

echo.
echo [*] 开始打包...
echo.

pyinstaller ^
    --onefile ^
    --windowed ^
    --name "MimoMonitor" ^
    --icon "NONE" ^
    --add-data "README.md;." ^
    tray_windows.py

echo.
if exist "dist\MimoMonitor.exe" (
    echo [+] 打包成功！
    echo     输出: dist\MimoMonitor.exe
    echo.
    echo [*] 使用方法：
    echo     1. 先在 WSL 启动服务器: cd ~/mimo ^&^& python main.py
    echo     2. 双击运行 dist\MimoMonitor.exe
) else (
    echo [-] 打包失败，请检查错误信息
)

pause
