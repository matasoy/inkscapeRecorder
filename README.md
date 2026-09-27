# 🎬 Inkscape Recorder

> **Non-intrusive, automated background time-lapse recorder and video generator for Inkscape artwork.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=flat&logo=windows&logoColor=white)](https://www.microsoft.com/)
[![Inkscape](https://img.shields.io/badge/Inkscape-1.0+-000000?style=flat&logo=inkscape&logoColor=white)](https://inkscape.org/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-Supported-007808?style=flat&logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Türkçe Dokümantasyon için tıklayın (Turkish README)](README.tr.md) | [Öğrenci Kullanım Kılavuzu](KULLANIM_KILAVUZU.txt)

---

## 🌟 Overview

**Inkscape Recorder** automatically captures your vector illustration process as you work in [Inkscape](https://inkscape.org/), compiling every change into a high-quality, time-lapse MP4 video. 

https://github.com/user-attachments/assets/28432973-afac-4ad2-a4e6-d459b241df1c

Unlike conventional screen recorders, **Inkscape Recorder runs completely in the background**:
- It **does not record your desktop** or screen coordinates.
- It **never steals window focus** or interrupts your drawing flow.
- It exports clean, high-resolution vector snapshots directly via the Inkscape CLI.
- It creates a dedicated `<project_name>_recorder` folder right next to your SVG document for both frames and the final MP4.

---

## ✨ Features

- **🎯 Smart Window Detection (HWND-Targeted):**  
  Automatically detects running Inkscape windows. Even if multiple documents or windows are open, actions are strictly targeted to your chosen artwork.
- **⚡ Background Autosave & Non-Intrusive Capture:**  
  Sends save commands in the background without forcing the Inkscape window to the foreground. You can browse the web or switch applications freely while recording.
- **📁 Automatic Path Resolution:**  
  Locates the active SVG on disk using GTK recent-file records (`recently-used.xbel`) and process handles. Output directory defaults to `<filename>_recorder/` right beside your artwork, but remains fully customizable.
- **🎞 Fluid 30 FPS CFR Video Export:**  
  Generates smooth constant frame rate (CFR) MP4 videos via FFmpeg, eliminating black screen delays or timestamp freezing.
- **🎬 Title Card & Project Watermark:**  
  Features an automated 3-second intro card showcasing the final artwork thumbnail along with your project filename, plus optional corner watermarks.
- **🖼 Responsive Live Frame Gallery:**  
  A modern dark-themed thumbnail gallery that wraps responsively as your window resizes. Click any thumbnail to preview it instantly in full resolution.
- **🛡 Student & Classroom Ready (Zero-Warning Portable Package):**  
  Includes a standalone portable build bundled with an officially signed Python runtime, completely bypassing Windows 11 Smart App Control and SmartScreen security blocks.

---

## 📦 Requirements

| Component | Minimum Version | Note |
|---|---|---|
| **OS** | Windows 10 / 11 (64-bit) | Win32 API integration |
| **Inkscape** | 1.0 or newer | Required for CLI rendering (`--export-type=png`) |
| **FFmpeg** | Any recent build | Required for MP4 video export |
| **Python** | 3.10+ (if running from source) | `customtkinter`, `pillow`, `pywinauto`, `psutil` |

---

## 🚀 Quick Start

### Option 1: Standalone Portable (Recommended for Users & Students)
No installation or administrator privileges required:
1. Download `InkscapeRecorder_Portable.zip` from [Releases](../../releases).
2. Extract the ZIP anywhere on your system.
3. Double-click **`Baslat.vbs`** (or `Baslat.bat`).
4. The application opens instantly without opening background command consoles.

### Option 2: Running from Source

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/inkscapeRecorder.git
   cd inkscapeRecorder
   ```

2. **Run automatic setup:**
   ```cmd
   install.bat
   ```
   *(This creates a `.venv` virtual environment and installs all dependencies.)*

3. **Launch the application:**
   ```cmd
   run.bat
   ```
   *Or manually:*
   ```cmd
   .venv\Scripts\activate
   python main.py
   ```

### Option 3: Installing FFmpeg
If FFmpeg is not already on your system PATH, install it via:
```powershell
# Using WinGet
winget install Gyan.FFmpeg

# Or using Chocolatey
choco install ffmpeg
```
*Alternatively, download `ffmpeg.exe` from [ffmpeg.org](https://ffmpeg.org/download.html) and place it directly into the application folder.*

---

## 📖 How to Use

```text
  1. Open & Save SVG  -->  2. Launch Recorder  -->  3. Hit "START RECORDING"  -->  4. Draw & Export MP4
```

1. **Open Inkscape and Save Your File:**  
   Open Inkscape and save your drawing at least once (`Ctrl + S`) as an `.svg` file (e.g., `my_drawing.svg`).
2. **Select Window in Inkscape Recorder:**  
   The program automatically detects your open document. Its location and the output folder (`my_drawing_recorder`) will be pre-filled.
3. **Set Interval & Start:**  
   Choose your capture frequency (e.g., 5s, 30s, 1m) and click **▶ START RECORDING**.
4. **Draw Naturally:**  
   Continue your artwork in Inkscape. Each time you save (`Ctrl + S`) or the timer lapses, a pristine snapshot is taken in the background.
5. **Export MP4:**  
   When finished, click **⏹ STOP RECORDING**, select your desired playback FPS (e.g., 1.0 FPS for step-by-step or 10.0 FPS for fast timelapse), and click **🎬 EXPORT MP4**.

---

## 🛠 Project Structure

```
inkscapeRecorder/
├── main.py                 # Modern CustomTkinter GUI application
├── recorder.py             # Recording engine (HWND tracking, CLI snapshot & FFmpeg)
├── build_portable.py       # Builder script for student portable package
├── build_portable.bat      # Batch launcher for portable package compilation
├── build_exe.bat           # PyInstaller single-executable builder
├── install.bat             # Environment setup and dependency installer
├── run.bat                 # Application launcher via virtual environment
├── sign_exe.ps1            # Code signing utility for Windows binaries
├── app.manifest            # High-DPI and Windows visual styling manifest
├── requirements.txt        # Python package dependencies
├── KULLANIM_KILAVUZU.txt   # Step-by-step student user guide (Turkish)
├── README.tr.md            # Turkish documentation
└── README.md               # English project documentation
```

---

## 🏗 Building & Distribution

### Building the Portable Package (Zero Smart App Control Blocks)
```cmd
build_portable.bat
```
Generates a self-contained ZIP archive in `dist_portable/` containing Python's officially signed runtime, required libraries, and launcher scripts.

### Building Single EXE
```cmd
build_exe.bat
```
Uses PyInstaller to compile `dist/InkscapeRecorder.exe`.

---

## 🤝 Contributing

Contributions, feature suggestions, and bug reports are welcome!
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.
