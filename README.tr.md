# Inkscape Recorder (Türkçe Dokümantasyon)

Inkscape'te çalışırken canvas değişikliklerini otomatik olarak arka planda kaydeder ve hızlandırılmış (time-lapse) MP4 video olarak export eder.

> 🇬🇧 **English documentation:** For English README, see [README.md](README.md).  
> 📖 **Öğrenci Kılavuzu:** Adım adım öğrenci kullanım kılavuzu için [KULLANIM_KILAVUZU.txt](KULLANIM_KILAVUZU.txt) dosyasını inceleyin.

---

## Nasıl Çalışır?

1. **Açık Inkscape Pencerelerini Otomatik Algılar:** Açık olan Inkscape pencereleri taranır ve listelenir.
2. **SVG Konumunu ve Çıktı Klasörünü Otomatik Tespit Eder:** Açık belgenin diskteki tam konumu otomatik bulunur ve projenin hemen yanında `<dosyaadı>_recorder` klasörü oluşturulur.
3. **Arka Planda Periyodik Kayıt:** Seçili Inkscape penceresine (HWND ile) `Ctrl+S` gönderilir. Kullanıcı çalışırken pencereler öne fırlamaz, çalışma engellenmez.
4. **Değişiklik Algılama & Temiz Snapshot:** Dosyada değişiklik yapılmışsa Inkscape CLI ile sayfa alanına göre beyaz arkaplanlı yüksek kaliteli PNG snapshot alınır.
5. **MP4 Video Export:** FFmpeg ile tüm kareler 30 fps CFR olarak akıcı bir MP4 videoya dönüştürülür. İlk 3 saniyede projenin adı ve son karenin önizlemesiyle şık bir başlık kartı eklenir.

https://github.com/user-attachments/assets/28432973-afac-4ad2-a4e6-d459b241df1c

---

## Kurulum ve Çalıştırma

### 1. Taşınabilir (Portable) Sürüm (Kurulum Gerektirmez - Önerilen)
Öğrencilere veya son kullanıcılara dağıtım için en sorunsuz yöntemdir. Windows 11 Smart App Control veya SmartScreen uyarısı vermez.
- `dist_portable\InkscapeRecorder_Portable.zip` dosyasını çıkartın.
- `Baslat.vbs` dosyasına çift tıklayın.

### 2. Kaynak Koddan Çalıştırma
```bash
# Kurulum scripti (.venv oluşturur ve paketleri yükler)
install.bat

# Uygulamayı başlat
run.bat
```

veya manuel:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 3. FFmpeg Gereksinimi
Video export işlemi için sisteminizde FFmpeg bulunmalıdır:
- **Windows (Winget):** `winget install Gyan.FFmpeg`
- **Chocolatey:** `choco install ffmpeg`
- **Manuel:** [ffmpeg.org](https://ffmpeg.org/download.html) üzerinden indirip `ffmpeg.exe` dosyasını proje klasörüne veya `C:\ffmpeg\bin\` altına yerleştirin.

---

## Proje Geliştirme Scriptleri

| Dosya | Açıklama |
|---|---|
| `run.bat` | Sanal ortamda uygulamayı başlatır. |
| `install.bat` | Python sanal ortamını ve bağımlılıklarını kurar. |
| `build_portable.bat` | Dağıtılabilir sıfır-uyarılı taşınabilir ZIP paketini üretir. |
| `build_exe.bat` | Tek parça bağımsız `.exe` derler. |
| `sign_exe.ps1` | Derlenen `.exe` dosyasını yerel kod imzalama sertifikası ile imzalar. |
