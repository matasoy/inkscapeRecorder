# trust_cert.ps1 - Windows'a bu sertifikayı tanıtma
$cert = Get-ChildItem -Path Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Subject -like "*InkscapeRecorder*" } | Select-Object -First 1

if (-not $cert) {
    Write-Host "[HATA] Sertifika bulunamadi! Once build_exe.bat calistirin." -ForegroundColor Red
    pause
    exit 1
}

$cerPath = Join-Path $PSScriptRoot "InkscapeRecorder.cer"
Export-Certificate -Cert $cert -FilePath $cerPath | Out-Null
Write-Host "[*] Sertifika cikarildi: $cerPath" -ForegroundColor Cyan

# Windows certutil ile Kullanici Kok Sertifika Deposuna ekle
Write-Host "[*] Sertifika Windows Guvenilen Depoya yukleniyor..." -ForegroundColor Yellow
certutil -user -addstore Root $cerPath
certutil -user -addstore TrustedPublisher $cerPath

Write-Host ""
Write-Host "[BASARILI] InkscapeRecorder sertifikasi Windows tarafindan guvenilir kabul edildi!" -ForegroundColor Green
Write-Host "Artik dist\InkscapeRecorder.exe dosyasini Smart App Control engeli olmadan acabilirsiniz." -ForegroundColor Green
Write-Host ""
pause
