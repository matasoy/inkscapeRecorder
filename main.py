"""
Inkscape Recorder — GUI Application
Modern dark-theme arayüz, customtkinter tabanlı.
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from datetime import datetime
import json

try:
    import customtkinter as ctk
except ImportError:
    print("customtkinter yüklü değil. Yükleniyor...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "customtkinter"], check=True)
    import customtkinter as ctk

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from recorder import (
    InkscapeRecorder,
    find_inkscape,
    find_ffmpeg,
    get_inkscape_windows,
    resolve_svg_path,
)

# ── Theme ─────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT     = "#4F8EF7"
ACCENT_DIM = "#2D5BCC"
BG_DARK    = "#0F1117"
BG_MID     = "#181C27"
BG_CARD    = "#1E2235"
BG_HOVER   = "#252A40"
TEXT_PRI   = "#EAEDF5"
TEXT_SEC   = "#7B8099"
SUCCESS    = "#34D399"
WARNING    = "#FBBF24"
ERROR      = "#F87171"
REC_RED    = "#EF4444"


# ── Thumbnail helper ──────────────────────────────────────────────────────────
def make_thumb(path: str, size=(120, 80)) -> "ImageTk.PhotoImage | None":
    if not PIL_AVAILABLE:
        return None
    try:
        img = Image.open(path).convert("RGB")
        img.thumbnail(size, Image.LANCZOS)
        # Pad to exact size
        padded = Image.new("RGB", size, (30, 35, 50))
        ox = (size[0] - img.width) // 2
        oy = (size[1] - img.height) // 2
        padded.paste(img, (ox, oy))
        return ImageTk.PhotoImage(padded)
    except Exception:
        return None


# ── Main Application ──────────────────────────────────────────────────────────
class InkscapeRecorderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Inkscape Recorder")
        self.geometry("1100x740")
        self.minsize(920, 620)
        self.configure(fg_color=BG_DARK)

        # State
        self.recorder: InkscapeRecorder | None = None
        self.is_recording = False
        self._countdown = 0
        self._countdown_thread: threading.Thread | None = None
        self._thumb_refs: list = []  # Prevent GC
        self._frame_cards: list = []  # Grid kart widget'ları
        self._current_cols: int = 3
        self._relayout_job = None
        self._empty_label = None

        # Window tracking state
        self.inkscape_windows: list[dict] = []
        self.selected_window: dict | None = None
        self.selected_hwnd: int | None = None

        # Output directory customization tracking
        self._custom_output_dir: bool = False

        # Settings (persistent)
        self.settings_path = Path.home() / ".inkscape_recorder_settings.json"
        self.settings = self._load_settings()
        saved_out = self.settings.get("output_dir", "")
        if saved_out and not saved_out.endswith("_recorder") and not saved_out.endswith("_frames"):
            self._custom_output_dir = True

        self._build_ui()
        self._apply_settings()
        self._refresh_inkscape_windows(auto_select_first=True)
        self._update_status("Hazır — Kaydı başlatabilirsiniz.", TEXT_SEC)

    # ── Settings persistence ──────────────────────────────────────────────────
    def _load_settings(self) -> dict:
        defaults = {
            "last_doc": "",
            "svg_path": "",
            "output_dir": "",
            "interval": 20,
            "fps": 1.0,
            "intro_enabled": True,
            "show_filename": True,
            "filename_pos": "Giriş Kartı",
            "inkscape_path": find_inkscape(),
            "ffmpeg_path": find_ffmpeg(),
        }
        try:
            if self.settings_path.exists():
                with open(self.settings_path) as f:
                    saved = json.load(f)
                defaults.update(saved)
        except Exception:
            pass
        return defaults

    def _save_settings(self):
        last_doc = ""
        if self.selected_window:
            last_doc = self.selected_window.get("doc_name", "")

        self.settings.update({
            "last_doc": last_doc,
            "svg_path": self.svg_var.get(),
            "output_dir": self.output_var.get(),
            "interval": int(self.interval_slider.get()),
            "fps": float(self.fps_var.get()),
            "intro_enabled": getattr(self, "intro_var", tk.BooleanVar(value=True)).get(),
            "show_filename": getattr(self, "show_filename_var", tk.BooleanVar(value=True)).get(),
            "filename_pos": getattr(self, "filename_pos_var", tk.StringVar(value="Giriş Kartı")).get(),
            "inkscape_path": self.inkscape_path_var.get(),
            "ffmpeg_path": self.ffmpeg_path_var.get(),
        })
        try:
            with open(self.settings_path, "w") as f:
                json.dump(self.settings, f, indent=2)
        except Exception:
            pass

    def _apply_settings(self):
        self.svg_var.set(self.settings.get("svg_path", ""))
        self.output_var.set(self.settings.get("output_dir", ""))
        self.interval_slider.set(self.settings.get("interval", 20))
        self._on_interval_change(self.settings.get("interval", 20))
        self.fps_var.set(str(self.settings.get("fps", 1.0)))

        if hasattr(self, "intro_var"):
            self.intro_var.set(self.settings.get("intro_enabled", True))
        if hasattr(self, "show_filename_var"):
            self.show_filename_var.set(self.settings.get("show_filename", True))
        if hasattr(self, "filename_pos_var"):
            self.filename_pos_var.set(self.settings.get("filename_pos", "Giriş Kartı"))

        # inkscape.com yerine daima inkscape.exe tercih edilir (konsol penceresi açılmaz)
        ink = self.settings.get("inkscape_path", "") or find_inkscape()
        if ink.lower().endswith("inkscape.com"):
            exe_cand = ink[:-4] + ".exe"
            if os.path.exists(exe_cand):
                ink = exe_cand
        self.inkscape_path_var.set(ink)
        self.ffmpeg_path_var.set(self.settings.get("ffmpeg_path", ""))

    # ── UI Build ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Header ───────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=BG_MID, height=60, corner_radius=0)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="⏺  Inkscape Recorder",
            font=ctk.CTkFont("Segoe UI", 20, "bold"),
            text_color=TEXT_PRI,
        ).pack(side="left", padx=24, pady=0)

        ctk.CTkLabel(
            header,
            text="SVG değişikliklerini otomatik kaydeder → MP4 export",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=TEXT_SEC,
        ).pack(side="left", padx=4)

        # ── Main area ─────────────────────────────────────────────────────────
        main = ctk.CTkFrame(self, fg_color=BG_DARK)
        main.pack(fill="both", expand=True, padx=0, pady=0)
        main.columnconfigure(0, weight=0, minsize=320)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        # Left panel
        self._build_left_panel(main)
        # Right panel
        self._build_right_panel(main)

        # ── Status bar ────────────────────────────────────────────────────────
        self._build_status_bar()

    def _build_left_panel(self, parent):
        left = ctk.CTkScrollableFrame(
            parent, fg_color=BG_MID, width=310, corner_radius=0,
            scrollbar_button_color=BG_CARD,
        )
        left.grid(row=0, column=0, sticky="nsew")

        pad = {"padx": 16, "pady": 6}

        # ── Inkscape Window Selection ─────────────────────────────────────────
        self._section_with_action(
            left,
            title="🖥 Inkscape Penceresi",
            btn_text="🔄 Yenile",
            btn_cmd=lambda: self._refresh_inkscape_windows(auto_select_first=True),
        )

        self.inkscape_menu_var = tk.StringVar(value="Inkscape aranıyor...")
        self.inkscape_menu = ctk.CTkOptionMenu(
            left,
            values=["Inkscape aranıyor..."],
            variable=self.inkscape_menu_var,
            command=self._on_inkscape_window_selected,
            fg_color=BG_CARD,
            button_color=BG_HOVER,
            dropdown_fg_color=BG_CARD,
            text_color=TEXT_PRI,
            height=36,
            dynamic_resizing=False,
        )
        self.inkscape_menu.pack(fill="x", **pad)

        self.inkscape_status_lbl = ctk.CTkLabel(
            left,
            text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=TEXT_SEC,
            wraplength=275,
            justify="left",
            anchor="w",
        )
        self.inkscape_status_lbl.pack(fill="x", padx=16, pady=(0, 4))

        # ── SVG File ──────────────────────────────────────────────────────────
        self._section(left, "📄 SVG Dosyası")

        self.svg_var = tk.StringVar()
        svg_row = ctk.CTkFrame(left, fg_color="transparent")
        svg_row.pack(fill="x", **pad)
        self.svg_entry = ctk.CTkEntry(
            svg_row, textvariable=self.svg_var,
            placeholder_text="Otomatik tespit edilir veya seçin",
            fg_color=BG_CARD, border_color=BG_HOVER, text_color=TEXT_PRI,
            height=36,
        )
        self.svg_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(
            svg_row, text="Seç", width=50, height=36,
            fg_color=BG_CARD, hover_color=BG_HOVER,
            text_color=ACCENT, corner_radius=8,
            command=self._browse_svg,
        ).pack(side="right")

        self.svg_auto_badge = ctk.CTkLabel(
            left,
            text="",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=SUCCESS,
            wraplength=275,
            justify="left",
            anchor="w",
        )
        self.svg_auto_badge.pack(fill="x", padx=16, pady=(0, 6))

        # ── Output Dir ────────────────────────────────────────────────────────
        self._section(left, "📁 Çıktı Klasörü")

        self.output_var = tk.StringVar()
        out_row = ctk.CTkFrame(left, fg_color="transparent")
        out_row.pack(fill="x", **pad)
        self.output_entry = ctk.CTkEntry(
            out_row, textvariable=self.output_var,
            placeholder_text="Örn: dosyaadı_recorder",
            fg_color=BG_CARD, border_color=BG_HOVER, text_color=TEXT_PRI,
            height=36,
        )
        self.output_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.output_entry.bind("<Key>", lambda e: setattr(self, "_custom_output_dir", True))
        ctk.CTkButton(
            out_row, text="Seç", width=50, height=36,
            fg_color=BG_CARD, hover_color=BG_HOVER,
            text_color=ACCENT, corner_radius=8,
            command=self._browse_output,
        ).pack(side="right")

        # ── Interval ──────────────────────────────────────────────────────────
        self._section(left, "⏱ Kayıt Aralığı")

        interval_row = ctk.CTkFrame(left, fg_color="transparent")
        interval_row.pack(fill="x", padx=16, pady=(4, 0))

        self.interval_label = ctk.CTkLabel(
            interval_row, text="20 saniye",
            font=ctk.CTkFont("Segoe UI", 24, "bold"),
            text_color=ACCENT,
        )
        self.interval_label.pack(side="left")
        ctk.CTkLabel(
            interval_row, text="de bir snapshot",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=TEXT_SEC,
        ).pack(side="left", padx=6, pady=(8, 0))

        self.interval_slider = ctk.CTkSlider(
            left, from_=5, to=120, number_of_steps=23,
            command=self._on_interval_change,
            button_color=ACCENT, button_hover_color=ACCENT_DIM,
            progress_color=ACCENT, fg_color=BG_CARD,
        )
        self.interval_slider.pack(fill="x", padx=16, pady=(4, 8))

        hint_row = ctk.CTkFrame(left, fg_color="transparent")
        hint_row.pack(fill="x", padx=16, pady=(0, 8))
        for label, val in [("5s", 5), ("30s", 30), ("1dk", 60), ("2dk", 120)]:
            ctk.CTkButton(
                hint_row, text=label, width=44, height=24,
                fg_color=BG_CARD, hover_color=BG_HOVER,
                text_color=TEXT_SEC, font=ctk.CTkFont("Segoe UI", 11),
                corner_radius=6,
                command=lambda v=val: self._set_interval(v),
            ).pack(side="left", padx=3)

        # ── Record Button ─────────────────────────────────────────────────────
        self._section(left, "🎬 Kayıt")

        self.record_btn = ctk.CTkButton(
            left,
            text="▶  KAYDI BAŞLAT",
            height=44,
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            fg_color=SUCCESS, hover_color="#22B57A",
            text_color="#0a1a10",
            corner_radius=10,
            command=self._toggle_recording,
        )
        self.record_btn.pack(fill="x", padx=16, pady=(4, 6))

        # Compact stats & countdown strip (tek satırda: Kare | Süre | Kalan)
        stats = ctk.CTkFrame(left, fg_color=BG_CARD, corner_radius=8)
        stats.pack(fill="x", padx=16, pady=(0, 8))
        stats.columnconfigure((0, 2, 4), weight=1)

        self.frame_count_label = self._compact_stat_item(stats, "Kare:", "0", 0, ACCENT)
        self._divider_v(stats, 1)
        self.rec_time_label   = self._compact_stat_item(stats, "Süre:", "0:00", 2, TEXT_PRI)
        self._divider_v(stats, 3)
        self.countdown_label  = self._compact_stat_item(stats, "Kalan:", "--", 4, SUCCESS)

        self.countdown_frame  = None
        self._rec_start_time  = None

        # ── Export ────────────────────────────────────────────────────────────
        self._section(left, "📥 Video Export")

        fps_row = ctk.CTkFrame(left, fg_color="transparent")
        fps_row.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(fps_row, text="FPS:", text_color=TEXT_SEC,
                     font=ctk.CTkFont("Segoe UI", 13)).pack(side="left")
        self.fps_var = tk.StringVar(value="1.0")
        fps_menu = ctk.CTkOptionMenu(
            fps_row,
            values=["0.5", "1.0", "2.0", "5.0", "10.0", "24.0", "30.0"],
            variable=self.fps_var,
            fg_color=BG_CARD, button_color=BG_HOVER,
            dropdown_fg_color=BG_CARD, text_color=TEXT_PRI,
            width=90,
        )
        fps_menu.pack(side="left", padx=8)
        ctk.CTkLabel(fps_row, text="kare/sn", text_color=TEXT_SEC,
                     font=ctk.CTkFont("Segoe UI", 11)).pack(side="left")

        # Girişte son kareyi gösterme seçeneği (İlk 3 sn)
        self.intro_var = tk.BooleanVar(value=True)
        intro_cb = ctk.CTkCheckBox(
            left,
            text="Girişte bitmiş hali göster (3 sn)",
            variable=self.intro_var,
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=TEXT_PRI,
            fg_color=ACCENT, hover_color=ACCENT_DIM,
            border_color=TEXT_SEC, border_width=1,
            checkbox_width=18, checkbox_height=18, corner_radius=4,
        )
        intro_cb.pack(fill="x", padx=16, pady=(6, 2))

        # Dosya adını ekrana yazma seçeneği
        self.show_filename_var = tk.BooleanVar(value=True)
        name_cb = ctk.CTkCheckBox(
            left,
            text="Dosya adını ekrana yaz",
            variable=self.show_filename_var,
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=TEXT_PRI,
            fg_color=ACCENT, hover_color=ACCENT_DIM,
            border_color=TEXT_SEC, border_width=1,
            checkbox_width=18, checkbox_height=18, corner_radius=4,
        )
        name_cb.pack(fill="x", padx=16, pady=(2, 4))

        opt_row = ctk.CTkFrame(left, fg_color="transparent")
        opt_row.pack(fill="x", padx=16, pady=(0, 6))
        ctk.CTkLabel(
            opt_row, text="Yazı konumu:", text_color=TEXT_SEC,
            font=ctk.CTkFont("Segoe UI", 11)
        ).pack(side="left")
        self.filename_pos_var = tk.StringVar(value="Giriş Kartı")
        pos_menu = ctk.CTkOptionMenu(
            opt_row,
            values=["Giriş Kartı", "Köşe Filigranı", "Her İkisi"],
            variable=self.filename_pos_var,
            fg_color=BG_CARD, button_color=BG_HOVER,
            dropdown_fg_color=BG_CARD, text_color=TEXT_PRI,
            height=26, width=125, font=ctk.CTkFont("Segoe UI", 11),
        )
        pos_menu.pack(side="right")

        self.export_btn = ctk.CTkButton(
            left,
            text="🎞  MP4'e Export Et",
            height=44,
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_DIM,
            text_color="white",
            corner_radius=12,
            command=self._export_video,
        )
        self.export_btn.pack(fill="x", padx=16, pady=(4, 4))

        ctk.CTkButton(
            left,
            text="🗑  Frame'leri Temizle",
            height=36,
            font=ctk.CTkFont("Segoe UI", 12),
            fg_color="transparent", hover_color=BG_HOVER,
            text_color=ERROR, border_color=ERROR, border_width=1,
            corner_radius=10,
            command=self._clear_frames,
        ).pack(fill="x", padx=16, pady=(0, 8))

        # ── Settings (collapsible) ────────────────────────────────────────────
        self._section(left, "⚙ Yol Ayarları")

        ctk.CTkLabel(left, text="Inkscape:", text_color=TEXT_SEC,
                     font=ctk.CTkFont("Segoe UI", 11), anchor="w").pack(fill="x", padx=16)
        self.inkscape_path_var = tk.StringVar()
        ink_row = ctk.CTkFrame(left, fg_color="transparent")
        ink_row.pack(fill="x", padx=16, pady=(2, 6))
        ctk.CTkEntry(
            ink_row, textvariable=self.inkscape_path_var,
            placeholder_text="inkscape.exe yolu",
            fg_color=BG_CARD, border_color=BG_HOVER, text_color=TEXT_PRI,
            height=32, font=ctk.CTkFont("Segoe UI", 11),
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(
            ink_row, text="...", width=36, height=32,
            fg_color=BG_CARD, hover_color=BG_HOVER, text_color=ACCENT,
            corner_radius=6,
            command=lambda: self._browse_exe(self.inkscape_path_var),
        ).pack(side="right")

        ctk.CTkLabel(left, text="FFmpeg:", text_color=TEXT_SEC,
                     font=ctk.CTkFont("Segoe UI", 11), anchor="w").pack(fill="x", padx=16)
        self.ffmpeg_path_var = tk.StringVar()
        ff_row = ctk.CTkFrame(left, fg_color="transparent")
        ff_row.pack(fill="x", padx=16, pady=(2, 16))
        ctk.CTkEntry(
            ff_row, textvariable=self.ffmpeg_path_var,
            placeholder_text="ffmpeg.exe yolu",
            fg_color=BG_CARD, border_color=BG_HOVER, text_color=TEXT_PRI,
            height=32, font=ctk.CTkFont("Segoe UI", 11),
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(
            ff_row, text="...", width=36, height=32,
            fg_color=BG_CARD, hover_color=BG_HOVER, text_color=ACCENT,
            corner_radius=6,
            command=lambda: self._browse_exe(self.ffmpeg_path_var),
        ).pack(side="right")

    def _build_right_panel(self, parent):
        right = ctk.CTkFrame(parent, fg_color=BG_DARK, corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew", padx=(1, 0))
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        # ── Toolbar ───────────────────────────────────────────────────────────
        toolbar = ctk.CTkFrame(right, fg_color=BG_MID, height=48, corner_radius=0)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.pack_propagate(False)

        ctk.CTkLabel(
            toolbar, text="📷 Frame Önizleme",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=TEXT_PRI,
        ).pack(side="left", padx=16)

        self.total_frames_label = ctk.CTkLabel(
            toolbar, text="0 frame",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=TEXT_SEC,
        )
        self.total_frames_label.pack(side="left", padx=4)

        # Zoom control
        ctk.CTkLabel(toolbar, text="Zoom:", text_color=TEXT_SEC,
                     font=ctk.CTkFont("Segoe UI", 11)).pack(side="right", padx=(0, 4))
        self.zoom_var = tk.IntVar(value=2)
        ctk.CTkSegmentedButton(
            toolbar,
            values=["S", "M", "L"],
            command=self._on_zoom_change,
            fg_color=BG_CARD,
            selected_color=ACCENT, selected_hover_color=ACCENT_DIM,
            unselected_color=BG_CARD, unselected_hover_color=BG_HOVER,
            text_color=TEXT_PRI,
        ).pack(side="right", padx=12)

        # ── Scrollable frame grid ─────────────────────────────────────────────
        self.frames_container = ctk.CTkScrollableFrame(
            right, fg_color=BG_DARK,
            scrollbar_button_color=BG_CARD,
        )
        self.frames_container.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.frames_container.bind("<Configure>", self._on_container_resize)
        self._thumb_size = (160, 110)
        self._update_empty_state()

    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, fg_color=BG_MID, height=32, corner_radius=0)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self.rec_indicator = ctk.CTkLabel(
            bar, text="⏹", font=ctk.CTkFont("Segoe UI", 13),
            text_color=TEXT_SEC, width=28,
        )
        self.rec_indicator.pack(side="left", padx=(10, 2))

        self.status_label = ctk.CTkLabel(
            bar, text="",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=TEXT_SEC, anchor="w",
        )
        self.status_label.pack(side="left", fill="x", expand=True, padx=4)

        # FFmpeg indicator
        ff = find_ffmpeg()
        ff_color = SUCCESS if ff else ERROR
        ff_text  = "✔ FFmpeg" if ff else "✘ FFmpeg yok"
        ctk.CTkLabel(
            bar, text=ff_text,
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=ff_color,
        ).pack(side="right", padx=12)

        ink = find_inkscape()
        ink_color = SUCCESS if ink else ERROR
        ink_text  = "✔ Inkscape" if ink else "✘ Inkscape yok"
        ctk.CTkLabel(
            bar, text=ink_text,
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=ink_color,
        ).pack(side="right", padx=(0, 4))

    # ── Helper widget builders ────────────────────────────────────────────────
    def _section(self, parent, title: str):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=16, pady=(14, 2))
        ctk.CTkLabel(
            f, text=title,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=TEXT_SEC,
        ).pack(side="left")
        ctk.CTkFrame(f, fg_color=BG_HOVER, height=1).pack(
            side="left", fill="x", expand=True, padx=(8, 0), pady=6
        )

    def _section_with_action(self, parent, title: str, btn_text: str, btn_cmd):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", padx=16, pady=(14, 2))
        ctk.CTkLabel(
            f, text=title,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=TEXT_SEC,
        ).pack(side="left")
        ctk.CTkButton(
            f, text=btn_text, width=64, height=24,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            fg_color=BG_CARD, hover_color=BG_HOVER,
            text_color=ACCENT, corner_radius=6,
            command=btn_cmd,
        ).pack(side="right")
        ctk.CTkFrame(f, fg_color=BG_HOVER, height=1).pack(
            side="left", fill="x", expand=True, padx=(8, 8), pady=6
        )

    def _compact_stat_item(self, parent, label: str, value: str, col: int, val_color: str = TEXT_PRI) -> ctk.CTkLabel:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=col, pady=5, padx=6)
        ctk.CTkLabel(
            frame, text=label,
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=TEXT_SEC,
        ).pack(side="left", padx=(0, 4))
        val_lbl = ctk.CTkLabel(
            frame, text=value,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=val_color,
        )
        val_lbl.pack(side="left")
        return val_lbl

    def _stat_widget(self, parent, value: str, label: str, col: int) -> ctk.CTkLabel:
        """Geriye dönük uyumluluk için."""
        return self._compact_stat_item(parent, f"{label}:", value, col)

    def _divider_v(self, parent, col):
        ctk.CTkFrame(parent, fg_color=BG_HOVER, width=1, height=16).grid(
            row=0, column=col, sticky="ns", pady=6
        )

    # ── Inkscape Window Management ────────────────────────────────────────────
    def _refresh_inkscape_windows(self, auto_select_first: bool = True):
        self.inkscape_windows = get_inkscape_windows()

        if not self.inkscape_windows:
            self.selected_window = None
            self.selected_hwnd = None
            self.inkscape_menu.configure(values=["Açık Inkscape bulunamadı"])
            self.inkscape_menu_var.set("Açık Inkscape bulunamadı")
            self.inkscape_status_lbl.configure(
                text="⚠️ Açık Inkscape penceresi bulunamadı. Inkscape'i açıp 'Yenile'ye basın.",
                text_color=WARNING,
            )
            if not self.svg_var.get():
                self.svg_auto_badge.configure(
                    text="ℹ Inkscape açık değilse manuel olarak bir SVG seçebilirsiniz.",
                    text_color=TEXT_SEC,
                )
            return

        values = [w["display_name"] for w in self.inkscape_windows]
        self.inkscape_menu.configure(values=values)

        # Hangi pencerenin seçileceğini belirle
        chosen = None
        last_doc = self.settings.get("last_doc", "")
        if last_doc:
            for w in self.inkscape_windows:
                if w["doc_name"].lower() == last_doc.lower():
                    chosen = w
                    break

        # Kaydedilmiş ve dosya yolu çözülmüş pencereyi önceliklendir
        if not chosen:
            for w in self.inkscape_windows:
                if w["is_saved"] and w["svg_path"]:
                    chosen = w
                    break
        if not chosen:
            for w in self.inkscape_windows:
                if w["is_saved"]:
                    chosen = w
                    break
        if not chosen:
            chosen = self.inkscape_windows[0]

        self._select_inkscape_window(chosen)

        count = len(self.inkscape_windows)
        if count == 1:
            self.inkscape_status_lbl.configure(
                text="✅ 1 Inkscape penceresi algılandı ve otomatik seçildi.",
                text_color=SUCCESS,
            )
        else:
            self.inkscape_status_lbl.configure(
                text=f"ℹ {count} Inkscape penceresi açık. Kaydedilecek olanı seçin.",
                text_color=ACCENT,
            )

    def _on_inkscape_window_selected(self, choice: str):
        for w in self.inkscape_windows:
            if w["display_name"] == choice:
                self._select_inkscape_window(w)
                break

    def _select_inkscape_window(self, win: dict):
        self.selected_window = win
        self.selected_hwnd = win["hwnd"]
        self.inkscape_menu_var.set(win["display_name"])

        # Eğer svg_path boşsa tekrar çözmeyi dene
        svg_path = win.get("svg_path", "")
        if not svg_path and win.get("is_saved"):
            svg_path = resolve_svg_path(win["doc_name"], win["pid"])
            win["svg_path"] = svg_path

        # SVG yolu otomatik tespiti
        if svg_path and Path(svg_path).exists():
            self.svg_var.set(svg_path)
            # Çıktı klasörünü de otomatik öner (kaynak dosyanın yanında dosyaadı_recorder)
            p = Path(svg_path)
            if not self._custom_output_dir or not self.output_var.get():
                out_folder = str(p.parent / f"{p.stem}_recorder")
                self.output_var.set(out_folder)
            self.svg_auto_badge.configure(
                text=f"✔ SVG konumu otomatik bağlandı: {p.name}",
                text_color=SUCCESS,
            )
        elif not win["is_saved"]:
            self.svg_auto_badge.configure(
                text="⚠️ Bu belge henüz kaydedilmemiş! Inkscape'te Ctrl+S ile kaydedip 'Yenile'ye basın.",
                text_color=WARNING,
            )
        else:
            self.svg_auto_badge.configure(
                text=f"🟡 '{win['doc_name']}' konumu otomatik bulunamadı. Lütfen 'Seç' butonuyla SVG'yi gösterin.",
                text_color=WARNING,
            )

    # ── Events ────────────────────────────────────────────────────────────────
    def _browse_svg(self):
        p = filedialog.askopenfilename(
            title="SVG dosyasını seçin",
            filetypes=[("SVG dosyaları", "*.svg"), ("Tüm dosyalar", "*.*")],
        )
        if p:
            self.svg_var.set(p)
            self.svg_auto_badge.configure(
                text="✔ Manuel seçildi",
                text_color=SUCCESS,
            )
            # Auto-set output dir next to SVG (dosyaadı_recorder)
            p_obj = Path(p)
            if not self._custom_output_dir or not self.output_var.get():
                self.output_var.set(str(p_obj.parent / f"{p_obj.stem}_recorder"))

    def _browse_output(self):
        initial = self.output_var.get()
        if not initial and self.svg_var.get():
            try:
                initial = str(Path(self.svg_var.get()).parent)
            except Exception:
                pass
        p = filedialog.askdirectory(title="Çıktı klasörü seçin", initialdir=initial or None)
        if p:
            self.output_var.set(p)
            self._custom_output_dir = True

    def _browse_exe(self, var: tk.StringVar):
        p = filedialog.askopenfilename(
            filetypes=[("Çalıştırılabilir", "*.exe *.com"), ("Tüm", "*.*")]
        )
        if p:
            var.set(p)

    def _on_interval_change(self, val):
        val = int(float(val))
        if val < 60:
            self.interval_label.configure(text=f"{val} saniye")
        else:
            m = val // 60
            s = val % 60
            self.interval_label.configure(text=f"{m}:{s:02d} dk")

    def _set_interval(self, val: int):
        self.interval_slider.set(val)
        self._on_interval_change(val)

    def _on_zoom_change(self, val: str):
        sizes = {"S": (110, 75), "M": (160, 110), "L": (220, 150)}
        self._thumb_size = sizes.get(val, (160, 110))
        self._current_cols = self._calculate_cols()
        self._refresh_thumbnails()

    def _update_status(self, msg: str, color: str = TEXT_PRI):
        self.status_label.configure(text=msg, text_color=color)

    # ── Recording controls ────────────────────────────────────────────────────
    def _toggle_recording(self):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        svg = self.svg_var.get().strip()
        out = self.output_var.get().strip()

        if not svg:
            messagebox.showwarning(
                "Eksik Bilgi",
                "Lütfen bir SVG dosyası seçin veya açık bir Inkscape penceresi belirleyin."
            )
            return
        if not out and svg:
            p = Path(svg)
            out = str(p.parent / f"{p.stem}_recorder")
            self.output_var.set(out)
        if not out:
            messagebox.showwarning("Eksik Bilgi", "Lütfen çıktı klasörü seçin.")
            return
        if not Path(svg).exists():
            messagebox.showerror(
                "Hata",
                f"SVG dosyası bulunamadı:\n{svg}\n\nEğer Inkscape'te yeni bir belge oluşturduysanız lütfen önce Inkscape içinden 'Ctrl+S' ile kaydedin."
            )
            return

        self._save_settings()
        interval = int(self.interval_slider.get())

        target_hwnd = self.selected_hwnd
        target_title = self.selected_window.get("title", "") if self.selected_window else ""

        self.recorder = InkscapeRecorder(
            svg_path=svg,
            output_dir=out,
            interval=interval,
            target_hwnd=target_hwnd,
            target_title=target_title,
            inkscape_path=self.inkscape_path_var.get() or find_inkscape(),
            on_frame_captured=self._on_frame_captured,
            on_status_change=self._on_status_update,
            on_error=self._on_error,
        )
        self.recorder.start()
        self.is_recording = True
        self._rec_start_time = time.time()

        # Update UI
        self.record_btn.configure(
            text="⏹  KAYDEDIYORUM...",
            fg_color=REC_RED, hover_color="#B91C1C",
            text_color="white",
        )
        self.rec_indicator.configure(text="🔴", text_color=REC_RED)
        if self.countdown_frame:
            self.countdown_frame.pack(fill="x", padx=16, pady=(0, 8))

        # Start countdown timer
        self._countdown = interval
        self._start_countdown(interval)

        # Start elapsed time updater
        self._start_elapsed_timer()

    def _stop_recording(self):
        if self.recorder:
            self.recorder.stop()
        self.is_recording = False

        self.record_btn.configure(
            text="▶  KAYDI BAŞLAT",
            fg_color=SUCCESS, hover_color="#22B57A",
            text_color="#0a1a10",
        )
        self.rec_indicator.configure(text="⏹", text_color=TEXT_SEC)
        if self.countdown_frame:
            self.countdown_frame.pack_forget()
        self.countdown_label.configure(text="--")
        self._save_settings()

    def _start_countdown(self, total: int):
        def tick(remaining):
            if not self.is_recording:
                return
            self.countdown_label.configure(text=f"{remaining}s")
            if remaining > 0:
                self.after(1000, tick, remaining - 1)
            else:
                self.after(1000, tick, total)  # Reset
        self.after(0, tick, total)

    def _start_elapsed_timer(self):
        def update():
            if not self.is_recording:
                return
            elapsed = int(time.time() - self._rec_start_time)
            m = elapsed // 60
            s = elapsed % 60
            self.rec_time_label.configure(text=f"{m}:{s:02d}")
            self.after(1000, update)
        self.after(1000, update)

    # ── Callbacks from recorder ───────────────────────────────────────────────
    def _on_frame_captured(self, frame_info: dict):
        self.after(0, self._add_frame_thumb, frame_info)
        count = self.recorder.frame_count if self.recorder else 0
        self.after(0, lambda: self.frame_count_label.configure(text=str(count)))
        self.after(0, lambda: self.total_frames_label.configure(text=f"{count} frame"))

    def _on_status_update(self, msg: str):
        self.after(0, self._update_status, msg, TEXT_PRI)

    def _on_error(self, msg: str):
        self.after(0, self._update_status, f"⚠ {msg}", ERROR)

    # ── Thumbnail grid (Responsive Wrap) ──────────────────────────────────────
    def _calculate_cols(self) -> int:
        """Konteyner genişliğine ve kart boyutuna göre satırdaki sütun sayısını hesaplar."""
        try:
            width = self.frames_container.winfo_width()
        except Exception:
            width = 0
        if width <= 80:
            return 3
        card_total_w = self._thumb_size[0] + 28  # kart boyutu + padding + margin
        return max(1, (width - 25) // card_total_w)

    def _on_container_resize(self, event=None):
        """Pencere yeniden boyutlandırıldığında kartları dinamik alt satırlara yerleştirir."""
        if not self._frame_cards:
            return
        new_cols = self._calculate_cols()
        if new_cols != self._current_cols:
            self._current_cols = new_cols
            if self._relayout_job is not None:
                try:
                    self.after_cancel(self._relayout_job)
                except Exception:
                    pass
            self._relayout_job = self.after(35, self._relayout_cards)

    def _relayout_cards(self):
        """Mevcut kartları hesaplanan sütun sayısına göre grid üzerinde yeniden dizer."""
        self._relayout_job = None
        cols = self._current_cols or self._calculate_cols()
        for idx, card in enumerate(self._frame_cards):
            r = idx // cols
            c = idx % cols
            card.grid(row=r, column=c, padx=8, pady=8, sticky="nw")

    def _update_empty_state(self):
        """Hiç frame yoksa kullanıcıya bilgi mesajı gösterir, varsa kaldırır."""
        if len(self._frame_cards) == 0:
            if not hasattr(self, "_empty_label") or self._empty_label is None or not self._empty_label.winfo_exists():
                self._empty_label = ctk.CTkLabel(
                    self.frames_container,
                    text="📷 Henüz kaydedilmiş frame yok.\n\nKaydı başlattığınızda veya Inkscape'te çizim yapıp kaydettiğinizde\nsnapshot'lar burada alt satırlara dökülen responsive bir liste olarak listelenecektir.",
                    font=ctk.CTkFont("Segoe UI", 13),
                    text_color=TEXT_SEC,
                    justify="center",
                )
                self._empty_label.grid(row=0, column=0, padx=40, pady=80, sticky="nsew")
        else:
            if hasattr(self, "_empty_label") and self._empty_label and self._empty_label.winfo_exists():
                self._empty_label.destroy()
                self._empty_label = None

    def _add_frame_thumb(self, frame_info: dict):
        self._build_thumb_card(self.frames_container, frame_info)

    def _build_thumb_card(self, parent, frame_info: dict):
        self._update_empty_state()
        tw, th = self._thumb_size
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=8, cursor="hand2")

        idx = len(self._frame_cards)
        cols = self._calculate_cols()
        self._current_cols = cols
        row = idx // cols
        col = idx % cols
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nw")

        # Thumbnail
        img_lbl = ctk.CTkLabel(card, text="", width=tw, height=th)
        img_lbl.pack(padx=6, pady=(6, 2))

        if PIL_AVAILABLE:
            thumb = make_thumb(frame_info["path"], (tw, th))
            if thumb:
                img_lbl.configure(image=thumb)
                self._thumb_refs.append(thumb)

        # Frame number
        f_lbl = ctk.CTkLabel(
            card,
            text=f"Frame {frame_info['frame']}",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color=TEXT_PRI,
        )
        f_lbl.pack()

        # Timestamp
        try:
            dt = datetime.fromisoformat(frame_info["timestamp"])
            ts = dt.strftime("%H:%M:%S")
        except Exception:
            ts = "--:--:--"
        t_lbl = ctk.CTkLabel(
            card,
            text=ts,
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=TEXT_SEC,
        )
        t_lbl.pack(pady=(0, 6))

        # Tıklayınca büyük görseli sistem görüntüleyicisiyle aç
        def open_img(event=None):
            try:
                os.startfile(frame_info["path"])
            except Exception:
                pass

        card.bind("<Button-1>", open_img)
        img_lbl.bind("<Button-1>", open_img)
        f_lbl.bind("<Button-1>", open_img)
        t_lbl.bind("<Button-1>", open_img)

        self._frame_cards.append(card)

    def _refresh_thumbnails(self):
        # Clear existing
        for widget in self.frames_container.winfo_children():
            widget.destroy()
        self._thumb_refs.clear()
        self._frame_cards.clear()
        self._current_cols = self._calculate_cols()

        if not self.recorder or not self.recorder.frames:
            self._update_empty_state()
            return

        for frame_info in self.recorder.frames:
            self._build_thumb_card(self.frames_container, frame_info)

    # ── Export ────────────────────────────────────────────────────────────────
    def _export_video(self):
        if not self.recorder or self.recorder.frame_count == 0:
            messagebox.showwarning("Uyarı", "Henüz kaydedilmiş frame yok.")
            return

        svg_val = self.svg_var.get().strip()
        stem = Path(svg_val).stem if svg_val else "inkscape"

        # Varsayılan kayıt klasörü ve dosya adı
        default_dir = self.output_var.get().strip()
        if not default_dir and svg_val:
            default_dir = str(Path(svg_val).parent / f"{stem}_recorder")
        if not default_dir:
            default_dir = str(Path.home())

        try:
            os.makedirs(default_dir, exist_ok=True)
        except Exception:
            pass

        default_filename = f"{stem}_recording.mp4"

        out_path = filedialog.asksaveasfilename(
            title="Video kayıt yeri",
            initialdir=default_dir,
            initialfile=default_filename,
            defaultextension=".mp4",
            filetypes=[("MP4 Video", "*.mp4"), ("Tüm dosyalar", "*.*")],
        )
        if not out_path:
            return

        fps = float(self.fps_var.get())
        intro_sec = 3.0 if self.intro_var.get() else 0.0
        show_fname = self.show_filename_var.get()
        pos_mode = self.filename_pos_var.get()

        show_intro_title = show_fname and pos_mode in ("Giriş Kartı", "Her İkisi")
        show_corner_wm = show_fname and pos_mode in ("Köşe Filigranı", "Her İkisi")

        doc_name = ""
        if self.selected_window and self.selected_window.get("doc_name"):
            doc_name = self.selected_window["doc_name"]
        elif self.svg_var.get():
            doc_name = Path(self.svg_var.get()).name

        self.export_btn.configure(text="⏳ Export ediliyor...", state="disabled")
        self._update_status("🎞 Video oluşturuluyor, lütfen bekleyin...", ACCENT)

        def do_export():
            ok, result = self.recorder.export_video(
                output_path=out_path,
                fps=fps,
                ffmpeg_path=self.ffmpeg_path_var.get() or find_ffmpeg(),
                intro_duration=intro_sec,
                show_filename=show_intro_title,
                watermark_all=show_corner_wm,
                filename_text=doc_name,
                outro_duration=2.0,
            )
            self.after(0, self._export_done, ok, result)

        threading.Thread(target=do_export, daemon=True).start()

    def _export_done(self, ok: bool, result: str):
        self.export_btn.configure(text="🎞  MP4'e Export Et", state="normal")
        if ok:
            self._update_status(f"✅ Video kaydedildi: {result}", SUCCESS)
            if messagebox.askyesno(
                "Export Tamamlandı",
                f"Video başarıyla oluşturuldu!\n\n{result}\n\nKlasörü açmak ister misiniz?",
            ):
                os.startfile(str(Path(result).parent))
        else:
            self._update_status(f"❌ Export hatası", ERROR)
            messagebox.showerror("Export Hatası", result)

    def _clear_frames(self):
        if not self.recorder or self.recorder.frame_count == 0:
            return
        if messagebox.askyesno(
            "Onay",
            f"Tüm {self.recorder.frame_count} frame silinecek. Emin misiniz?",
        ):
            self.recorder.clear_frames()
            for w in self.frames_container.winfo_children():
                w.destroy()
            self._thumb_refs.clear()
            self._frame_cards.clear()
            self._update_empty_state()
            self.frame_count_label.configure(text="0")
            self.total_frames_label.configure(text="0 frame")
            self._update_status("🗑 Tüm frame'ler silindi.", WARNING)

    # ── Closing ───────────────────────────────────────────────────────────────
    def on_close(self):
        if self.is_recording:
            if not messagebox.askyesno(
                "Kayıt Devam Ediyor",
                "Kayıt devam ediyor. Yine de çıkmak istiyor musunuz?",
            ):
                return
        if self.recorder:
            self.recorder.stop()
        self._save_settings()
        self.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    app = InkscapeRecorderApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
