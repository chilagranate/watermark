# PyInstaller spec for Windows .exe
# Usage: pyinstaller build/win.spec

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).parent
VIDEOSEAL_DIR = None
for p in sys.path + [os.path.join(sys.exec_prefix, 'Lib', 'site-packages'), os.path.join(os.environ.get('VIRTUAL_ENV', ''), 'Lib', 'site-packages')]:
    vp = Path(p) / 'videoseal'
    if vp.exists():
        VIDEOSEAL_DIR = vp
        SITE_PACKAGES = vp.parent
        break

block_cipher = None

added_files = [
    (str(PROJECT_ROOT / 'watermark_app' / 'gui'), 'watermark_app/gui'),
]

if VIDEOSEAL_DIR:
    added_files.append((str(VIDEOSEAL_DIR / 'cards'), 'videoseal/cards'))
    added_files.append((str(VIDEOSEAL_DIR / 'configs'), 'videoseal/configs'))
    ckpts_dir = SITE_PACKAGES / 'ckpts'
    if ckpts_dir.exists():
        added_files.append((str(ckpts_dir), 'ckpts'))

a = Analysis(
    [str(PROJECT_ROOT / 'watermark_app' / 'server.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'watermark_app',
        'watermark_app.config',
        'watermark_app.database',
        'watermark_app.hasher',
        'watermark_app.marker_image',
        'watermark_app.marker_video',
        'watermark_app.payload',
        'watermark_app.sync',
        'watermark_app.version',
        'fastapi',
        'uvicorn',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'starlette',
        'dotenv',
        'httpx',
        'qrcode',
        'PIL',
        'imagehash',
        'cv2',
        'numpy',
        'torch',
        'torchvision',
        'torchvision.io',
        'torchvision.transforms',
        'videoseal',
        'videoseal.utils',
        'videoseal.models',
        'videoseal.models.videoseal',
        'videoseal.bwm_core',
        'omegaconf',
        'python_multipart',
        'websockets',
        'dtcwt',
        'pywt',
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
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Watermark',
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
    icon=None,
)
