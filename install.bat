@echo off
title Inkscape Recorder - Kurulum
cd /d "%~dp0"
echo.
echo ============================================
echo   Inkscape Recorder - Kurulum Basliyor
echo ============================================
echo.

:: Python yorumlayıcısını bul
set SYS_PYTHON=
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set SYS_PYTHON="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) else (
    python --version >nul 2>&1
    if %errorlevel% equ 0 (
        set SYS_PYTHON=python
    ) else (
        py --version >nul 2>&1
        if %errorlevel% equ 0 (
            set SYS_PYTHON=py
        )
    )
)

if "%SYS_PYTHON%"=="" (
    echo [HATA] Python bulunamadi!
    echo Python'u su adresten indirin:
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python bulundu: %SYS_PYTHON%
echo.

:: .venv olustur
if not exist ".venv\Scripts\python.exe" (
    echo [*] Sanal ortam (.venv) olusturuluyor...
    %SYS_PYTHON% -m venv .venv
    if %errorlevel% neq 0 (
        echo [HATA] Sanal ortam olusturulamadi!
        pause
        exit /b 1
    )
)

set VENV_PYTHON=.venv\Scripts\python.exe
set VENV_PIP=.venv\Scripts\pip.exe

echo [*] Bagimliliklar yukleniyor...
%VENV_PYTHON% -m pip install --upgrade pip
%VENV_PIP% install -r requirements.txt
%VENV_PIP% install pyinstaller

echo.
echo ============================================
echo   Kurulum Basariyla Tamamlandi!
echo ============================================
echo.
echo Uygulamayi calistirmak icin: run.bat
echo EXE olusturmak icin:        build_exe.bat
echo.
pause
