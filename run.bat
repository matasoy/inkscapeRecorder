@echo off
title Inkscape Recorder
cd /d "%~dp0"

:: 1. Once yerel sanal ortami (.venv) kontrol et
if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
    goto :run
)

:: 2. Sistem Python kontrolü
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON=python
    goto :run
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON=py
    goto :run
)

echo [HATA] Python bulunamadi. Once install.bat calistirin!
pause
exit /b 1

:run
%PYTHON% main.py
