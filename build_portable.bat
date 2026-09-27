@echo off
title Inkscape Recorder - Tasinabilir Paket Olusturucu
cd /d "%~dp0"
echo.
echo ========================================================
echo   Inkscape Recorder - Ogrenciler Icin Tasinabilir Paket
echo ========================================================
echo.

if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

%PYTHON% build_portable.py

pause
