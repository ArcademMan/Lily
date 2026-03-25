# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None
ROOT = os.path.abspath('.')

# ── Version info (riduce falsi positivi antivirus) ───────────────────────────
version_info = None
try:
    from PyInstaller.utils.win32.versioninfo import (
        VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable,
        StringStruct, VarFileInfo, VarStruct,
    )
    version_info = VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=(1, 0, 0, 0),
            prodvers=(1, 0, 0, 0),
            mask=0x3F,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
        ),
        kids=[
            StringFileInfo([
                StringTable('040904B0', [
                    StringStruct('CompanyName', 'AmMstools'),
                    StringStruct('FileDescription', 'Lily - Assistente Vocale'),
                    StringStruct('FileVersion', '1.0.0.0'),
                    StringStruct('InternalName', 'Lily'),
                    StringStruct('LegalCopyright', '© 2025 AmMstools'),
                    StringStruct('OriginalFilename', 'Lily.exe'),
                    StringStruct('ProductName', 'Lily'),
                    StringStruct('ProductVersion', '1.0.0.0'),
                ])
            ]),
            VarFileInfo([VarStruct('Translation', [0x0409, 1200])]),
        ],
    )
except Exception:
    pass

# ── Dati da includere ─────────────────────────────────────────────────────────
datas = [
    ('assets', 'assets'),
    ('es.exe', '.'),
    # winpty: agent e console necessari per il backend legacy (ConPTY crasha in frozen)
    (os.path.join(ROOT, '.venv', 'Lib', 'site-packages', 'winpty', 'winpty-agent.exe'), 'winpty'),
    (os.path.join(ROOT, '.venv', 'Lib', 'site-packages', 'winpty', 'OpenConsole.exe'), 'winpty'),
]

# ── Binari CUDA (lib/) ────────────────────────────────────────────────────────
binaries = []
lib_dir = os.path.join(ROOT, 'lib')
if os.path.isdir(lib_dir):
    for f in os.listdir(lib_dir):
        if f.endswith('.dll'):
            binaries.append((os.path.join(lib_dir, f), '.'))

# ── Hidden imports ────────────────────────────────────────────────────────────
hiddenimports = [
    # PySide6
    'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
    'PySide6.QtSvg', 'PySide6.QtSvgWidgets', 'PySide6.QtNetwork',
    # Audio
    'sounddevice', 'numpy',
    # Whisper
    'faster_whisper',
    'ctranslate2',
    # TTS
    'edge_tts', 'piper',
    # LLM
    'requests', 'httpx',
    # Windows
    'win32api', 'win32con', 'win32gui', 'win32process', 'win32com',
    'win32com.client', 'comtypes', 'pycaw', 'pycaw.pycaw',
    # Hotkey
    'keyboard',
    # UI icons
    'qtawesome',
    # Utils
    'psutil', 'json', 'threading', 'subprocess',
    # i18n (dynamic imports)
    'core.i18n.it', 'core.i18n.en',
    # OnnxRuntime (per piper/whisper)
    'onnxruntime',
]

# ── Esclusioni (alleggerisce il bundle) ───────────────────────────────────────
excludes = [
    'matplotlib', 'tkinter', 'unittest', 'test', 'tests',
    'pip', 'setuptools', 'wheel', 'distutils',
    'pytest', 'sphinx', 'docutils',
    'IPython', 'jupyter', 'notebook',
    'torch', 'torchvision', 'torchaudio',
    'tensorflow', 'tensorboard',
    'PyQt5', 'PyQt6',
]

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ['main.py'],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

# ── EXE ───────────────────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,          # onedir: binari separati
    name='Lily',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,                    # non strippare su Windows
    upx=False,                      # UPX disabilitato → meno falsi positivi
    console=False,                  # windowed, niente terminale
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
    version=version_info,           # metadata PE → meno falsi positivi
)

# ── COLLECT (onedir) ──────────────────────────────────────────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,                      # UPX disabilitato ovunque
    upx_exclude=[],
    name='Lily',
)
