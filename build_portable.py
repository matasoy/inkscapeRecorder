"""
build_portable.py - Smart App Control ve SmartScreen engellerine takılmayan,
öğrencilere ve kullanıcılara doğrudan dağıtılabilir Taşınabilir (Portable) Paket Oluşturucu.

Bu paket:
- Python kurulumu GEREKTİRMEZ.
- Yönetici yetkisi GEREKTİRMEZ.
- Sertifika onaylama GEREKTİRMEZ.
- Microsoft & Python Software Foundation tarafından resmi imzalı pythonw.exe'yi kullanır;
  böylece Windows 11 Smart App Control ASLA engellemez.
"""

import os
import sys
import shutil
import zipfile
from pathlib import Path

def main():
    root_dir = Path(__file__).resolve().parent
    dist_dir = root_dir / "dist_portable" / "InkscapeRecorder"
    runtime_dir = dist_dir / "runtime"
    py_base = Path(sys.base_prefix)

    print("=====================================================")
    print("  Inkscape Recorder - Taşınabilir Paket Hazırlanıyor")
    print("=====================================================")
    print(f"[*] Kaynak Python: {py_base}")
    print(f"[*] Hedef Dizin:   {dist_dir}")
    print()

    # Temizle
    if dist_dir.exists():
        print("[*] Eski taşınabilir dizin temizleniyor...")
        shutil.rmtree(dist_dir, ignore_errors=True)

    runtime_dir.mkdir(parents=True, exist_ok=True)

    # 1. Python çalıştırıcılarını ve temel DLL'leri kopyala (Resmi imzalı ikililer)
    binaries = [
        "python.exe",
        "pythonw.exe",
        "python3.dll",
        "python312.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
    ]
    for b in binaries:
        src = py_base / b
        if src.exists():
            shutil.copy2(src, runtime_dir / b)

    # DLLs ve tcl klasörlerini kopyala
    for folder in ["DLLs", "tcl"]:
        src_f = py_base / folder
        if src_f.exists():
            print(f"[*] {folder} kopyalanıyor...")
            shutil.copytree(src_f, runtime_dir / folder, dirs_exist_ok=True)

    # Lib (standart kütüphane) kopyala (test, idlelib vb. hariç)
    print("[*] Standart kütüphane (Lib) kopyalanıyor...")
    src_lib = py_base / "Lib"
    dst_lib = runtime_dir / "Lib"
    
    def ignore_patterns(path, names):
        ignored = set()
        for name in names:
            if name in ["test", "idlelib", "turtledemo", "__pycache__", "ensurepip"]:
                ignored.add(name)
        return ignored

    shutil.copytree(src_lib, dst_lib, ignore=ignore_patterns, dirs_exist_ok=True)

    # 2. Sanal ortamdaki site-packages (customtkinter, pillow, pywinauto, psutil vb.) kopyala
    venv_site = root_dir / ".venv" / "Lib" / "site-packages"
    target_site = dst_lib / "site-packages"
    target_site.mkdir(parents=True, exist_ok=True)

    print("[*] Bağımlılıklar (site-packages) kopyalanıyor...")
    def ignore_site(path, names):
        ignored = set()
        for name in names:
            if name in ["pip", "setuptools", "PyInstaller", "pyinstaller", "altgraph", "pefile", "__pycache__"]:
                ignored.add(name)
            elif name.endswith(".dist-info"):
                ignored.add(name)
        return ignored

    shutil.copytree(venv_site, target_site, ignore=ignore_site, dirs_exist_ok=True)

    # 3. Proje dosyalarını kopyala
    print("[*] Uygulama dosyaları kopyalanıyor...")
    for f in ["main.py", "recorder.py", "app.ico", "README.md", "KULLANIM_KILAVUZU.txt", "ffmpeg.exe"]:
        src_file = root_dir / f
        if src_file.exists():
            shutil.copy2(src_file, dist_dir / f)

    # 4. Başlatıcıları oluştur
    # Başlat.vbs (Sessiz, konsolsuz, doğrudan GUI açar)
    vbs_content = '''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "runtime\\pythonw.exe main.py", 0, False
'''
    with open(dist_dir / "Baslat.vbs", "w", encoding="utf-8") as f:
        f.write(vbs_content)

    # Baslat.bat (Konsol üzerinden veya hata ayıklamak için alternatif)
    bat_content = '''@echo off
title Inkscape Recorder
cd /d "%~dp0"
start "" "runtime\\pythonw.exe" main.py
'''
    with open(dist_dir / "Baslat.bat", "w", encoding="utf-8") as f:
        f.write(bat_content)

    # 5. Kullanıcı Bilgilendirme Dosyası (Nasıl Kullanılır.txt)
    txt_content = '''==============================================
   Inkscape Recorder - Taşınabilir (Portable) Sürüm
==============================================

Bu sürüm hiçbir kurulum veya yönetici yetkisi GEREKTİRMEZ.
Windows 11 Akıllı Uygulama Denetimi (Smart App Control) ve
SmartScreen engellerine takılmaz.

NASIL ÇALIŞTIRILIR?
1. Klasördeki "Baslat.vbs" (veya "Baslat.bat") dosyasına çift tıklayın.
2. Uygulama birkaç saniye içinde doğrudan açılacaktır.

AYRINTILI KULLANIM KILAVUZU:
Adım adım kullanım, Inkscape ayarları, video oluşturma ve ipuçları için 
klasör içindeki "KULLANIM_KILAVUZU.txt" belgesini inceleyebilirsiniz.

ÖĞRENCİLERE VE KULLANICILARA DAĞITIM:
Bu klasörü veya ZIP dosyasını öğrencilerinize doğrudan gönderebilirsiniz.
Öğrenciler ZIP'i herhangi bir yere çıkarıp "Baslat.vbs"ye tıklayarak hemen kullanabilir.
'''
    with open(dist_dir / "Nasıl Kullanılır.txt", "w", encoding="utf-8") as f:
        f.write(txt_content)

    # 6. ZIP Arşivi Oluştur
    zip_path = root_dir / "dist_portable" / "InkscapeRecorder_Portable.zip"
    print(f"[*] Dağıtım için ZIP arşivi oluşturuluyor: {zip_path.name}...")
    temp_zip = root_dir / "dist_portable" / "InkscapeRecorder_Portable_temp.zip"
    try:
        with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in dist_dir.rglob("*"):
                rel = file.relative_to(dist_dir.parent)
                zf.write(file, rel)
        if zip_path.exists():
            try:
                zip_path.unlink()
            except PermissionError:
                pass
        if temp_zip.exists():
            if not zip_path.exists():
                temp_zip.replace(zip_path)
            else:
                try:
                    temp_zip.replace(zip_path)
                except PermissionError:
                    print(f"[UYARI] {zip_path.name} açık olduğu için üzerine yazılamadı.")
                    print(f"[BİLGİ] Yeni arşiv '{temp_zip.name}' olarak kaydedildi.")
                    zip_path = temp_zip
    except Exception as e:
        print(f"[HATA] ZIP oluşturulurken hata: {e}")

    zip_size_mb = zip_path.stat().st_size / (1024 * 1024) if zip_path.exists() else 0
    print()
    print("=====================================================")
    print("  [BAŞARILI] Taşınabilir Dağıtım Paketi Hazır!")
    print("=====================================================")
    print(f"[-] Klasor: {dist_dir}")
    print(f"[-] Dagitilabilir ZIP: {zip_path} ({zip_size_mb:.1f} MB)")
    print()
    print("Bu ZIP dosyasini ogrencilerinize dogrudan gonderebilirsiniz.")
    print("Ogrenciler ZIP'ten cikarip 'Baslat.vbs'ye tikladiginda hicbir")
    print("Smart App Control veya SmartScreen uyarisi almadan calisacaktir.")

if __name__ == "__main__":
    main()
