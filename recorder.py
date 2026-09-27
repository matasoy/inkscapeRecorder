"""
Inkscape Recorder - Core Logic
Inkscape penceresine Ctrl+S göndererek SVG kaydeder,
değişiklik algılayınca PNG snapshot alır.
"""

import os
import time
import hashlib
import subprocess
import threading
import json
import shutil
import re
import urllib.parse
from datetime import datetime
from pathlib import Path
import ctypes
from ctypes import wintypes

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


INKSCAPE_COMMON_PATHS = [
    r"C:\Program Files\Inkscape\bin\inkscape.exe",
    r"C:\Program Files\Inkscape\bin\inkscape.com",
    r"C:\Program Files (x86)\Inkscape\bin\inkscape.exe",
]


CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def get_silent_subprocess_kwargs() -> dict:
    """Windows'ta subprocess çağrılarının siyah konsol penceresi açmasını tamamen engeller."""
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = CREATE_NO_WINDOW
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = si
    return kwargs


def find_inkscape() -> str:
    for path in INKSCAPE_COMMON_PATHS:
        if os.path.exists(path):
            return path
    if shutil.which("inkscape"):
        return "inkscape"
    return ""


def find_ffmpeg() -> str:
    # 1. Proje/uygulama yerel dizininde var mı?
    import sys
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend([
            exe_dir / "ffmpeg.exe",
            exe_dir / "runtime" / "ffmpeg.exe",
        ])
    script_dir = Path(__file__).resolve().parent
    candidates.extend([
        script_dir / "ffmpeg.exe",
        script_dir / "runtime" / "ffmpeg.exe",
    ])

    # 2. WinGet paketleri
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_dir = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        if winget_dir.exists():
            for p in winget_dir.glob("**/ffmpeg.exe"):
                candidates.append(p)
                break

    for c in candidates:
        if c.exists():
            return str(c)

    # 3. Sistem PATH
    if shutil.which("ffmpeg"):
        return "ffmpeg"

    # 4. Yaygın kurulum yolları
    common = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
    ]
    for p in common:
        if os.path.exists(p):
            return p
    return ""


# ── Inkscape Window & SVG Path Detection ───────────────────────────────────────

def _find_svg_in_xbel(doc_name: str) -> str:
    """
    GTK recently-used.xbel dosyasından Inkscape tarafından açılan/kaydedilen
    SVG dosyasının tam yolunu bulur.
    """
    xbel_candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "recently-used.xbel",
        Path(os.environ.get("APPDATA", "")) / "recently-used.xbel",
        Path.home() / ".recently-used.xbel",
    ]

    from xml.etree import ElementTree as ET

    for xbel_path in xbel_candidates:
        if not xbel_path.exists():
            continue
        try:
            tree = ET.parse(str(xbel_path))
            root = tree.getroot()
            # En son kaydedilenler sonda yer alır, tersten arıyoruz
            for bm in reversed(root.findall("bookmark")):
                href = bm.attrib.get("href", "")
                raw_path = urllib.parse.unquote(href, encoding="utf-8")
                if raw_path.startswith("file:///"):
                    clean_path = raw_path[8:].replace("/", "\\")
                    p = Path(clean_path)
                    # Belge adı eşleşmesi
                    if doc_name and p.name.lower() == doc_name.lower():
                        if p.exists():
                            return str(p.resolve())
                    # Eğer doc_name verilmemişse ve ilk bulunan SVG ise
                    elif not doc_name and p.suffix.lower() == ".svg" and p.exists():
                        for app in bm.iter():
                            if "inkscape" in app.attrib.get("name", "").lower():
                                return str(p.resolve())
        except Exception:
            pass
    return ""


def resolve_svg_path(doc_name: str, pid: int = 0) -> str:
    """
    Belge adı veya Inkscape PID'si üzerinden diskteki tam SVG yolunu bulur.
    Waterfall stratejisi:
    1. GTK recently-used.xbel (Inkscape yerel geçmişi)
    2. Process cmdline (psutil)
    3. Process open_files (psutil)
    4. Process working directory (psutil)
    5. Masaüstü, Belgeler, İndirilenler gibi yaygın klasörler
    """
    if not doc_name:
        return ""

    # 1. GTK recent files
    found = _find_svg_in_xbel(doc_name)
    if found:
        return found

    # 2. psutil ile process cmdline, open files veya cwd
    if PSUTIL_AVAILABLE and pid > 0:
        try:
            proc = psutil.Process(pid)
            # cmdline kontrolü
            for arg in proc.cmdline():
                p = Path(arg)
                if p.name.lower() == doc_name.lower() and p.exists():
                    return str(p.resolve())

            # open files kontrolü
            for f in proc.open_files():
                p = Path(f.path)
                if p.name.lower() == doc_name.lower() and p.exists():
                    return str(p.resolve())

            # cwd kontrolü
            cwd_candidate = Path(proc.cwd()) / doc_name
            if cwd_candidate.exists():
                return str(cwd_candidate.resolve())
        except Exception:
            pass

    # 3. Standart kullanıcı dizinlerini kontrol et
    search_dirs = [
        Path.home() / "Desktop",
        Path.home() / "OneDrive" / "Desktop",
        Path.home() / "Documents",
        Path.home() / "OneDrive" / "Documents",
        Path.home() / "Belgeler",
        Path.home() / "OneDrive" / "Belgeler",
        Path.home() / "Downloads",
        Path.home() / "İndirilenler",
        Path.cwd(),
    ]
    for d in search_dirs:
        candidate = d / doc_name
        if candidate.exists():
            return str(candidate.resolve())

    return ""


def get_inkscape_windows() -> list[dict]:
    """
    Sistemde açık olan tüm Inkscape pencerelerini tespit eder.
    Her pencere için şu bilgileri içeren liste döndürür:
    {
        'hwnd': int,
        'title': str,
        'pid': int,
        'doc_name': str,
        'is_saved': bool,
        'svg_path': str,
        'display_name': str,
    }
    """
def is_inkscape_process(pid: int) -> bool:
    """
    Sürecin kesinlikle gerçek Inkscape ('inkscape.exe') olup olmadığını doğrular.
    Kendi sürecimizi (InkscapeRecorder.exe/python), IDE pencerelerini vb. eler.
    """
    if pid <= 0 or pid == os.getpid():
        return False
    if PSUTIL_AVAILABLE:
        try:
            return psutil.Process(pid).name().lower() == "inkscape.exe"
        except Exception:
            return False
    kernel32 = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if h_proc:
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
                return Path(buf.value).name.lower() == "inkscape.exe"
        except Exception:
            pass
        finally:
            kernel32.CloseHandle(h_proc)
    return False


def get_inkscape_windows() -> list[dict]:
    """
    Sistemde açık olan tüm gerçek Inkscape pencerelerini tespit eder.
    Her pencere için şu bilgileri içeren liste döndürür:
    {
        'hwnd': int,
        'title': str,
        'pid': int,
        'doc_name': str,
        'is_saved': bool,
        'svg_path': str,
        'display_name': str,
    }
    """
    windows = []
    user32 = ctypes.windll.user32
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def enum_windows_callback(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True

        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value.strip()

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        p_id = pid.value

        # 1. Kesinlikle gerçek 'inkscape.exe' süreci olmalı! (IDE veya kendi penceremiz elenir)
        if not is_inkscape_process(p_id):
            return True

        # 2. Başlık filtresi: Kendi penceremiz veya ilgisiz pencereler olamaz
        lower_title = title.lower()
        if "inkscape recorder" in lower_title or "antigravity" in lower_title:
            return True

        # 3. Inkscape çizim/belge penceresi olmalı (dialog pencereleri değil)
        is_doc_window = (
            re.search(r"[-–—]\s*Inkscape(\s+\d.*)?$", title, re.IGNORECASE)
            or lower_title == "inkscape"
        )
        if not is_doc_window:
            return True

        # 4. Ana pencere olmalı (alt popup/araç çubuğu değil)
        owner = user32.GetWindow(hwnd, 4)  # GW_OWNER
        if owner == 0:
            windows.append((hwnd, p_id, title))

        return True

    user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)

    # Bulunan pencereleri analiz et
    results = []
    for hwnd, pid, title in windows:
        clean = title.lstrip("* ").strip()
        m = re.search(r"^(.*?)\s*[-–—]\s*Inkscape", clean, re.IGNORECASE)
        if m:
            doc_name = m.group(1).strip()
        else:
            doc_name = clean

        is_svg = doc_name.lower().endswith(".svg")
        is_unsaved = (
            not is_svg
            or "yeni belge" in doc_name.lower()
            or "new document" in doc_name.lower()
            or doc_name.lower() == "inkscape"
        )
        is_saved = not is_unsaved

        svg_path = ""
        if is_saved:
            svg_path = resolve_svg_path(doc_name, pid)

        # Dropdown etiketi
        if is_saved and svg_path:
            short_dir = Path(svg_path).parent.name
            display_name = f"🟢 {doc_name} ({short_dir}) [PID:{pid}]"
        elif is_saved:
            display_name = f"🟡 {doc_name} (Konum aranıyor) [PID:{pid}]"
        else:
            display_name = f"⚪ {doc_name} (Kaydedilmemiş) [PID:{pid}]"

        results.append({
            "hwnd": hwnd,
            "title": title,
            "pid": pid,
            "doc_name": doc_name,
            "is_saved": is_saved,
            "svg_path": svg_path,
            "display_name": display_name,
        })

    return results


class InkscapeRecorder:
    """
    SVG dosyasını izleyip, belirli aralıklarla seçili Inkscape penceresine
    Ctrl+S göndererek değişiklikleri PNG olarak kaydeden sınıf.
    """

    def __init__(
        self,
        svg_path: str,
        output_dir: str,
        interval: int = 20,
        target_hwnd: int | None = None,
        target_title: str = "",
        inkscape_path: str = "",
        on_frame_captured=None,
        on_status_change=None,
        on_error=None,
    ):
        self.svg_path = Path(svg_path)
        self.output_dir = Path(output_dir)
        self.interval = interval
        self.target_hwnd = target_hwnd
        self.target_title = target_title
        
        detected = inkscape_path or find_inkscape()
        if detected.lower().endswith("inkscape.com"):
            exe_cand = detected[:-4] + ".exe"
            if os.path.exists(exe_cand):
                detected = exe_cand
        self.inkscape_path = detected

        self.on_frame_captured = on_frame_captured
        self.on_status_change = on_status_change
        self.on_error = on_error

        self.is_running = False
        self._thread: threading.Thread | None = None
        self._last_hash: str | None = None
        self._metadata: list[dict] = []
        self._lock = threading.Lock()

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._load_metadata()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _status(self, msg: str):
        if self.on_status_change:
            self.on_status_change(msg)

    def _error(self, msg: str):
        if self.on_error:
            self.on_error(msg)

    def _get_file_hash(self) -> str | None:
        try:
            with open(self.svg_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None

    def _load_metadata(self):
        meta_file = self.output_dir / "metadata.json"
        if meta_file.exists():
            try:
                with open(meta_file, encoding="utf-8") as f:
                    self._metadata = json.load(f)
            except Exception:
                self._metadata = []

    def _save_metadata(self):
        meta_file = self.output_dir / "metadata.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(self._metadata, f, indent=2, ensure_ascii=False)

    # ── Inkscape communication ────────────────────────────────────────────────

    def _is_drawing_active(self) -> bool:
        """Kullanıcı şu anda mouse tuşunu basılı tutarak çizim yapıyor mu kontrol eder."""
        try:
            user32 = ctypes.windll.user32
            VK_LBUTTON = 0x01
            VK_RBUTTON = 0x02
            # 0x8000 biti tuşun şu an basılı olduğunu belirtir
            left_down = bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
            right_down = bool(user32.GetAsyncKeyState(VK_RBUTTON) & 0x8000)
            return left_down or right_down
        except Exception:
            return False

    def _send_save_to_inkscape(self, allow_activate: bool = False) -> bool:
        """
        Seçilen Inkscape penceresine Ctrl+S gönderir.
        Kullanıcı başka bir penceredeyse (örn. tarayıcı, notlar),
        asla odağı çalmaz ve Inkscape'i öne getirmez.
        """
        try:
            user32 = ctypes.windll.user32

            if not self.target_hwnd or not user32.IsWindow(self.target_hwnd):
                return False

            # 1. Simge durumundaysa (minimize) ASLA zorla ekrana getirme
            if user32.IsIconic(self.target_hwnd):
                return False

            # 2. Başlıkta '*' (kaydedilmemiş değişiklik) var mı?
            length = user32.GetWindowTextLengthW(self.target_hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(self.target_hwnd, buff, length + 1)
            title = buff.value.strip()

            # '*' ile başlamıyorsa zaten kaydedilmiştir veya değişiklik yoktur
            has_unsaved_changes = title.startswith("*")
            if not has_unsaved_changes:
                return True

            # 3. Odak kontrolü: Kullanıcı şu anda Inkscape penceresinde mi?
            current_fg = user32.GetForegroundWindow()
            is_active = (current_fg == self.target_hwnd)

            if not is_active:
                # Kullanıcı başka bir pencerede (tarayıcı, editör vb.)!
                # ASLA odağı çalma, kullanıcının çalışmasını bölme.
                if not allow_activate:
                    # Arka planda sessizce WM_KEYDOWN göndermeyi dene
                    WM_KEYDOWN = 0x0100
                    WM_KEYUP = 0x0101
                    VK_CONTROL = 0x11
                    VK_S = 0x53
                    user32.PostMessageW(self.target_hwnd, WM_KEYDOWN, VK_CONTROL, 0)
                    user32.PostMessageW(self.target_hwnd, WM_KEYDOWN, VK_S, 0)
                    user32.PostMessageW(self.target_hwnd, WM_KEYUP, VK_S, 0)
                    user32.PostMessageW(self.target_hwnd, WM_KEYUP, VK_CONTROL, 0)
                    return False

            # 4. Kullanıcı tam şu anda mouse ile fırça/çizgi mi çekiyor?
            if is_active and self._is_drawing_active():
                # Çizimi bölmemek için bu saniyeyi pas geç
                return False

            # 5. Inkscape aktifse Ctrl+S gönder
            import pywinauto
            app = pywinauto.Application(backend="win32").connect(
                handle=self.target_hwnd, timeout=2
            )
            window = app.window(handle=self.target_hwnd)

            if not is_active and allow_activate:
                try:
                    window.set_focus()
                except Exception:
                    user32.SetForegroundWindow(self.target_hwnd)
                time.sleep(0.1)

            window.type_keys("^s", with_spaces=False)
            time.sleep(0.3)
            return True
        except ImportError:
            return False
        except Exception:
            return False

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def _take_snapshot(self) -> bool:
        """Inkscape CLI ile SVG'yi PNG'ye dönüştürür."""
        if not self.inkscape_path:
            self._error("Inkscape yolu bulunamadı. Ayarlardan belirtin.")
            return False

        frame_num = len(self._metadata) + 1
        png_path = self.output_dir / f"frame_{frame_num:04d}.png"

        try:
            kwargs = get_silent_subprocess_kwargs()
            result = subprocess.run(
                [
                    self.inkscape_path,
                    str(self.svg_path),
                    "--export-type=png",
                    f"--export-filename={png_path}",
                    "--export-area-page",
                    "--export-background=white",
                    "--export-background-opacity=1.0",
                    "--export-dpi=96",
                ],
                capture_output=True,
                timeout=45,
                **kwargs,
            )

            if png_path.exists() and png_path.stat().st_size > 0:
                frame_info = {
                    "frame": frame_num,
                    "path": str(png_path),
                    "timestamp": datetime.now().isoformat(),
                    "hash": self._last_hash,
                }
                with self._lock:
                    self._metadata.append(frame_info)
                self._save_metadata()

                if self.on_frame_captured:
                    self.on_frame_captured(frame_info)
                return True
            else:
                self._error(f"Snapshot oluşturulamadı (frame {frame_num})")
                return False

        except subprocess.TimeoutExpired:
            self._error("Inkscape export zaman aşımı!")
            return False
        except Exception as e:
            self._error(f"Snapshot hatası: {e}")
            return False

    # ── Main recording loop ───────────────────────────────────────────────────

    def _run_loop(self):
        self._status("⏺ Kayıt başladı...")
        self._last_hash = self._get_file_hash()
        elapsed_seconds = 0
        user32 = ctypes.windll.user32

        while self.is_running:
            # 1. Her saniye dosya hash'ini kontrol et!
            # Kullanıcı ister Inkscape'te Ctrl+S yapmış olsun,
            # ister harici olarak kaydedilmiş olsun, anında yakalanır.
            new_hash = self._get_file_hash()
            if new_hash and new_hash != self._last_hash:
                self._last_hash = new_hash
                self._status("🔄 Değişiklik algılandı — snapshot alınıyor...")
                ok = self._take_snapshot()
                if ok:
                    self._status(f"✅ Frame {len(self._metadata)} kaydedildi")
                    elapsed_seconds = 0

            # 2. Otomatik kaydetme zamanı geldi mi?
            if elapsed_seconds >= self.interval:
                elapsed_seconds = 0
                current_fg = user32.GetForegroundWindow() if hasattr(user32, "GetForegroundWindow") else 0
                is_active = bool(self.target_hwnd and current_fg == self.target_hwnd)

                if is_active:
                    self._status("💾 Inkscape kaydediliyor...")
                    self._send_save_to_inkscape(allow_activate=False)
                elif self.target_hwnd:
                    # Kullanıcı başka bir pencerede: Asla odağı çalma!
                    self._send_save_to_inkscape(allow_activate=False)

            # Küçük aralıklarla uyu ki durdurma butonuna anında tepki versin
            for _ in range(10):
                if not self.is_running:
                    break
                time.sleep(0.1)
            elapsed_seconds += 1

        self._status("⏹ Kayıt durduruldu")

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        if self.is_running:
            return
        if not self.svg_path.exists():
            self._error(f"SVG dosyası bulunamadı: {self.svg_path}")
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.is_running = False

    def clear_frames(self):
        """Tüm frame'leri ve metadata'yı siler."""
        with self._lock:
            for frame in self._metadata:
                try:
                    Path(frame["path"]).unlink(missing_ok=True)
                except Exception:
                    pass
            self._metadata = []
        self._save_metadata()

    def export_video(
        self,
        output_path: str,
        fps: float = 1.0,
        ffmpeg_path: str = "",
        intro_duration: float = 3.0,
        show_filename: bool = True,
        watermark_all: bool = False,
        filename_text: str = "",
        outro_duration: float = 2.0,
        on_progress=None,
    ) -> tuple[bool, str]:
        """
        Kaydedilmiş frame'leri FFmpeg ile MP4'e dönüştürür.
        - intro_duration: İlk X saniye (varsayılan 3 sn) son karenin (bitmiş çizimin) resmi gösterilir.
        - show_filename: Giriş ekranında dosya adını şık bir başlık kartı olarak yazar.
        - watermark_all: Tüm video boyunca sol üst köşede dosya adı filigranı gösterir.
        - outro_duration: Video sonunda son kare X saniye (varsayılan 2 sn) sabit kalır.
        """
        with self._lock:
            frames = list(self._metadata)

        if not frames:
            return False, "Kaydedilmiş frame bulunamadı."

        ff = ffmpeg_path or find_ffmpeg()
        if not ff:
            return (
                False,
                "FFmpeg bulunamadı!\nhttps://ffmpeg.org/download.html adresinden indirin\nveya ayarlardan yolunu belirtin.",
            )

        # Geçici dosyalar
        list_file = self.output_dir / "_frames_list.txt"
        intro_file = self.output_dir / "_intro_preview.png"
        wm_file = self.output_dir / "_watermark.png"
        cleanup_targets = [list_file, intro_file, wm_file]

        def to_posix(p: str | Path) -> str:
            return Path(p).resolve().as_posix()

        duration = 1.0 / fps  # Her normal frame kaç saniye sürsün
        display_name = filename_text or (self.svg_path.name if self.svg_path else "Inkscape Çizimi")
        last_frame_path = frames[-1]["path"]

        try:
            with open(list_file, "w", encoding="utf-8") as f:
                # 1. GİRİŞ: İlk X saniye (varsayılan 3 sn) son karenin resmi
                if intro_duration > 0 and Path(last_frame_path).exists():
                    intro_img_to_use = last_frame_path
                    if show_filename:
                        ok_intro = self._create_intro_preview(
                            last_frame_path, display_name, str(intro_file), show_title=True
                        )
                        if ok_intro:
                            intro_img_to_use = str(intro_file)

                    f.write(f"file '{to_posix(intro_img_to_use)}'\n")
                    f.write(f"duration {intro_duration:.4f}\n")

                # 2. NORMAL TİMELAPSE: Kare 1'den son kareye kadar
                for frame in frames:
                    f.write(f"file '{to_posix(frame['path'])}'\n")
                    f.write(f"duration {duration:.4f}\n")

                # 3. ÇIKIŞ (OUTRO): Video aniden kesilmesin diye son kare 2 saniye kalsın
                if outro_duration > 0 and Path(last_frame_path).exists():
                    f.write(f"file '{to_posix(last_frame_path)}'\n")
                    f.write(f"duration {outro_duration:.4f}\n")

                # Concat demuxer için bitiş referansı
                f.write(f"file '{to_posix(last_frame_path)}'\n")

            # 4. FFmpeg Komutunu Derle
            # Tüm oynatıcılarda (Windows Media Player, web, mobil) anında ve sıfır gecikmeyle
            # açılması için MUTLAKA sabit kare hızı (CFR - 30 fps), tekdüze SAR (setsar=1)
            # ve düzenli keyframe (-g 30) kullanılır.
            cmd = [ff, "-y", "-f", "concat", "-safe", "0", "-i", to_posix(list_file)]

            has_watermark = False
            if watermark_all:
                if self._create_corner_watermark(display_name, str(wm_file)):
                    cmd.extend(["-loop", "1", "-i", to_posix(wm_file)])
                    has_watermark = True

            if has_watermark:
                filter_str = (
                    "[0:v]scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1,fps=30[base];"
                    "[base][1:v]overlay=24:24:shortest=1,format=yuv420p"
                )
                cmd.extend(["-filter_complex", filter_str])
            else:
                filter_str = "scale=trunc(iw/2)*2:trunc(ih/2)*2,setsar=1,fps=30,format=yuv420p"
                cmd.extend(["-vf", filter_str])

            cmd.extend([
                "-r", "30",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-g", "30",
                "-movflags", "+faststart",
                output_path,
            ])

            kwargs = get_silent_subprocess_kwargs()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                **kwargs,
            )

            for target in cleanup_targets:
                try:
                    target.unlink(missing_ok=True)
                except Exception:
                    pass

            if result.returncode == 0:
                return True, output_path
            else:
                return False, f"FFmpeg hatası:\n{result.stderr[-500:]}"

        except subprocess.TimeoutExpired:
            return False, "FFmpeg zaman aşımı (5 dakika)."
        except Exception as e:
            return False, f"Export hatası: {e}"

    def _create_intro_preview(
        self, base_path: str, filename_text: str, out_path: str, show_title: bool = True
    ) -> bool:
        """Giriş için son kare üzerine şık bir başlık kartı yerleştirir."""
        if not PIL_AVAILABLE or not os.path.exists(base_path):
            return False
        try:
            with Image.open(base_path) as base:
                raw_rgba = base.convert("RGBA")
                W, H = raw_rgba.size
                dpi = base.info.get("dpi", (96, 96))

                # Şeffaf kısımların siyah görünmesini önlemek için beyaz taban oluştur
                solid_bg = Image.new("RGBA", (W, H), (255, 255, 255, 255))
                img = Image.alpha_composite(solid_bg, raw_rgba)

                if show_title:
                    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                    draw = ImageDraw.Draw(overlay)

                    font_size_main = max(18, int(min(W, H) * 0.042))
                    font_size_sub = max(11, int(font_size_main * 0.62))

                    try:
                        font_main = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", font_size_main)
                        font_sub = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", font_size_sub)
                    except Exception:
                        try:
                            font_main = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_size_main)
                            font_sub = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size_sub)
                        except Exception:
                            font_main = ImageFont.load_default()
                            font_sub = font_main

                    text_main = filename_text
                    text_sub = "Tamamlanan Çizim • 3s Önizleme"

                    bbox_m = draw.textbbox((0, 0), text_main, font=font_main)
                    w_m, h_m = bbox_m[2] - bbox_m[0], bbox_m[3] - bbox_m[1]

                    bbox_s = draw.textbbox((0, 0), text_sub, font=font_sub)
                    w_s, h_s = bbox_s[2] - bbox_s[0], bbox_s[3] - bbox_s[1]

                    pad_x = int(font_size_main * 0.9)
                    pad_y = int(font_size_main * 0.5)

                    card_w = max(w_m, w_s) + pad_x * 2
                    card_h = h_m + h_s + pad_y * 2 + 6
                    card_x = (W - card_w) // 2
                    card_y = max(24, int(H * 0.04))

                    # Modern yarı saydam yuvarlatılmış kart
                    draw.rounded_rectangle(
                        [card_x, card_y, card_x + card_w, card_y + card_h],
                        radius=14,
                        fill=(15, 17, 23, 215),
                        outline=(79, 142, 247, 210),
                        width=2,
                    )

                    draw.text(
                        (card_x + (card_w - w_m) // 2, card_y + pad_y),
                        text_main,
                        font=font_main,
                        fill=(245, 247, 255, 255),
                    )
                    draw.text(
                        (card_x + (card_w - w_s) // 2, card_y + pad_y + h_m + 6),
                        text_sub,
                        font=font_sub,
                        fill=(123, 128, 153, 255),
                    )

                    img = Image.alpha_composite(img, overlay)

                img.save(out_path, format="PNG", dpi=dpi)
                return True
        except Exception:
            return False

    def _create_corner_watermark(self, filename_text: str, out_path: str) -> bool:
        """Tüm video boyunca sol üst köşede duracak şık bir dosya adı filigranı üretir."""
        if not PIL_AVAILABLE:
            return False
        try:
            font_size = 16
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", font_size)
            except Exception:
                try:
                    font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_size)
                except Exception:
                    font = ImageFont.load_default()

            temp_img = Image.new("RGBA", (1, 1))
            draw_temp = ImageDraw.Draw(temp_img)
            bbox = draw_temp.textbbox((0, 0), filename_text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

            pad_h = 14
            pad_v = 7
            badge_w = tw + pad_h * 2 + 14
            badge_h = th + pad_v * 2

            badge = Image.new("RGBA", (badge_w, badge_h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(badge)
            draw.rounded_rectangle(
                [0, 0, badge_w - 1, badge_h - 1],
                radius=7,
                fill=(15, 17, 23, 190),
                outline=(79, 142, 247, 180),
                width=1,
            )

            # Mavi gösterge noktası
            dot_r = 4
            dot_x = pad_h
            dot_y = badge_h // 2
            draw.ellipse(
                [dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r],
                fill=(79, 142, 247, 255),
            )

            draw.text(
                (pad_h + 12, pad_v - 1),
                filename_text,
                font=font,
                fill=(240, 243, 250, 255),
            )
            badge.save(out_path, format="PNG")
            return True
        except Exception:
            return False

    @property
    def frame_count(self) -> int:
        return len(self._metadata)

    @property
    def frames(self) -> list[dict]:
        with self._lock:
            return list(self._metadata)

    @property
    def remaining_seconds(self) -> int:
        """Sonraki snapshot'a kalan saniye (tahmini)."""
        return self.interval
