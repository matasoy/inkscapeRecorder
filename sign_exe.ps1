# sign_exe.ps1 - Windows Authenticode Code Signing Script
$ErrorActionPreference = "Continue"

$exePath = Join-Path $PSScriptRoot "dist\InkscapeRecorder.exe"

if (-not (Test-Path $exePath)) {
    Write-Host "[HATA] $exePath bulunamadi!" -ForegroundColor Red
    exit 1
}

Write-Host "[*] Kod imzalama sertifikasi araniyor..." -ForegroundColor Cyan

# Mevcut sertifikayi ara
$cert = Get-ChildItem -Path Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Subject -like "*InkscapeRecorder*" } | Select-Object -First 1

if (-not $cert) {
    Write-Host "[*] Yeni yerel Kod Imzalama Sertifikasi olusturuluyor..." -ForegroundColor Yellow
    $cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject "CN=InkscapeRecorder" `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -NotAfter (Get-Date).AddYears(5)
}

Write-Host "[OK] Sertifika hazir: $($cert.Subject)" -ForegroundColor Green

# EXE'yi imzala
Write-Host "[*] EXE dosyasi SHA256 ile dijital olarak imzalaniyor..." -ForegroundColor Cyan
Set-AuthenticodeSignature -Certificate $cert -FilePath $exePath -HashAlgorithm SHA256

# Mark of the Web (Zone.Identifier) engelini kaldir
Unblock-File -Path $exePath -ErrorAction SilentlyContinue

$sig = Get-AuthenticodeSignature -FilePath $exePath
Write-Host "[SONUC] Imza Durumu: $($sig.Status)" -ForegroundColor Green
Write-Host "[SONUC] Imzalayan: $($sig.SignerCertificate.Subject)" -ForegroundColor Green
Write-Host "[OK] InkscapeRecorder.exe basariyla imzalandi!" -ForegroundColor Green
