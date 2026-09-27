# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = []
binaries = [('ffmpeg.exe', '.')] if os.path.exists('ffmpeg.exe') else []
hiddenimports = [
    'pywinauto',
    'comtypes',
    'comtypes.client',
    'win32gui',
    'win32process',
    'win32con',
    'win32api',
    'psutil',
    'PIL',
    'PIL.Image',
    'PIL.ImageTk',
]

# CustomTkinter tema ve font asset'lerinin tamamını topla
ctk_datas, ctk_binaries, ctk_hidden = collect_all('customtkinter')
datas += ctk_datas
binaries += ctk_binaries
hiddenimports += ctk_hidden

# Pillow modülleri
hiddenimports += collect_submodules('PIL')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='InkscapeRecorder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app.ico'],
    version='version_info.txt',
    manifest='app.manifest',
)
