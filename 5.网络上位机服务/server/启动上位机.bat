@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
    echo Python not found. Please install Python 3.11 or activate the daq-server environment.
    pause
    exit /b 1
)

python main.py
pause
