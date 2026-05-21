@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ======================================
echo   NL2SQL Prototype
echo ======================================
echo.
echo [1/2] Запуск сервера на http://localhost:8000
echo.

:: Открыть браузер
start "" http://localhost:8000

:: Запуск сервера
python api_server.py

:: Если Python не найден — пробуем python3
if errorlevel 1 (
    python3 api_server.py
)

:: Если всё равно ошибка
if errorlevel 1 (
    cls
    echo ======================================
    echo   ОШИБКА ЗАПУСКА
    echo ======================================
    echo.
    echo Python не найден. Установите Python 3:
    echo https://www.python.org/downloads/
    echo.
    echo Или запустите вручную:
    echo   cd prototype
    echo   python api_server.py
    echo.
    pause
)

