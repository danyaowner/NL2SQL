@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1

echo ======================================
echo   NL2SQL Prototype
echo ======================================
echo.
echo Starting server at http://localhost:8000
echo Browser will open automatically...
echo.

py api_server.py
if errorlevel 1 (
    python api_server.py
)
if errorlevel 1 (
    python3 api_server.py
)
if errorlevel 1 (
    cls
    echo ======================================
    echo   START ERROR
    echo ======================================
    echo.
    echo Python not found. Install from:
    echo https://www.python.org/downloads/
    echo.
    pause
)
