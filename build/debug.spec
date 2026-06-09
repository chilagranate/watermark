# PyInstaller spec for Windows .exe (debug version - minimal test)
import os
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).parent

block_cipher = None

added_files = [
    (str(PROJECT_ROOT / 'watermark_app' / 'gui'), 'watermark_app/gui'),
    (str(PROJECT_ROOT / 'build' / 'videoseal_data' / 'cards'), 'videoseal/cards'),
    (str(PROJECT_ROOT / 'build' / 'videoseal_data' / 'configs'), 'videoseal/configs'),
]

a = Analysis(
    [str(PROJECT_ROOT / 'build' / 'debug_entry.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'torch', 'torchvision', 'videoseal', 'PIL', 'fastapi', 'uvicorn',
        'watermark_app.config', 'watermark_app.marker_image',
        'omegaconf', 'python_multipart', 'websockets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='WatermarkDebug',
    debug=False, bootloader_ignore_signals=False, strip=False,
    upx=True, upx_exclude=[], runtime_tmpdir=None,
    console=True, disable_windowed_traceback=False,
    argv_emulation=False, target_arch=None,
    codesign_identity=None, entitlements_file=None, icon=None,
)
