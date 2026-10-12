@echo off
setlocal enabledelayedexpansion
title PrivDoc - Privacy-First Document Converter
cd /d "%~dp0"

echo ========================================================
echo   PrivDoc - Privacy-First Document Suite
echo ========================================================

REM 1. Detect Python executable across standard environments
set "PYTHON_EXE="

if defined PYTHON_PATH if exist "%PYTHON_PATH%" set "PYTHON_EXE=%PYTHON_PATH%"

if not defined PYTHON_EXE if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=.venv\Scripts\python.exe"
)

if not defined PYTHON_EXE if exist "%APPDATA%\uv\python\cpython-3.12-windows-x86_64-none\python.exe" (
    set "PYTHON_EXE=%APPDATA%\uv\python\cpython-3.12-windows-x86_64-none\python.exe"
)

if not defined PYTHON_EXE (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 --version >nul 2>&1
        if not errorlevel 1 set "PYTHON_EXE=py -3"
    )
)

if not defined PYTHON_EXE (
    where python >nul 2>&1
    if not errorlevel 1 (
        python --version >nul 2>&1
        if not errorlevel 1 set "PYTHON_EXE=python"
    )
)

if not defined PYTHON_EXE (
    echo [ERROR] No working Python 3.10+ interpreter detected.
    echo Please install Python (3.10+) or set the PYTHON_PATH environment variable.
    echo Download: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo   Localhost URL: http://localhost:5000
echo   Security:      Restricted to local machine (127.0.0.1)
echo ========================================================

start "" http://localhost:5000
%PYTHON_EXE% run.py
if errorlevel 1 (
    echo.
    echo [ERROR] PrivDoc server stopped with an error code.
    echo If Python dependencies are missing, install them with:
    echo   %PYTHON_EXE% -m pip install -r requirements.txt
    echo.
    pause
)
