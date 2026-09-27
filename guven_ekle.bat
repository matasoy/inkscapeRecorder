@echo off
title Inkscape Recorder - Windows Guvenlik Sertifikasi Yukleyici
cd /d "%~dp0"
echo.
echo =========================================================
echo   Inkscape Recorder - Windows Guvenlik Onayi Yukleyici
echo =========================================================
echo.
echo Bu islem, olusturulan EXE dosyasini Windows Akilli Uygulama
echo Denetimi (Smart App Control) ve SmartScreen tarafindan
echo taninir ve guvenilir hale getirir.
echo.
echo Acilacak Windows iletisim kutusunda "Evet" / "Yukle"yi secin.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File trust_cert.ps1
