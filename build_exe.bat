@echo off
title Inkscape Recorder - EXE Olusturucu
cd /d "%~dp0"
echo.
echo ===================================================
echo   Inkscape Recorder - PyInstaller EXE Olusturucu
echo ===================================================
echo.

:: Venv icindeki pyinstaller'i kontrol et
if exist ".venv\Scripts\pyinstaller.exe" (
    set PYINSTALLER=.venv\Scripts\pyinstaller.exe
) else (
    pyinstaller --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYINSTALLER=pyinstaller
    ) else (
        echo [HATA] PyInstaller bulunamadi!
        echo Lutfen once install.bat calistirin.
        pause
        exit /b 1
    )
)

echo [*] PyInstaller bulundu: %PYINSTALLER%
echo [*] EXE derleme islemi baslatiliyor (bu islem 1-2 dakika surebilir)...
echo.

%PYINSTALLER% InkscapeRecorder.spec --clean --noconfirm

if %errorlevel% equ 0 (
    echo.
    echo [*] Windows Guvenligi ve SmartScreen icin dijital imzalama yapiliyor...
    powershell -NoProfile -ExecutionPolicy Bypass -File sign_exe.ps1
    echo.
    echo ===================================================
    echo   [BASARILI] EXE Basariyla Olusturuldu ve Imzalandi!
    echo ===================================================
    echo.
    echo Olusturulan dosya: dist\InkscapeRecorder.exe
    echo.
    echo Bu tek dosyayi dilediginiz yere tasiyarak
    echo Python kurulu olmayan sistemlerde de calistirabilirsiniz.
    echo.
) else (
    echo.
    echo [HATA] EXE olusturma sirasinda bir hata meydana geldi!
    echo.
)

pause
