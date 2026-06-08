# PyInstaller spec for macOS .app bundle
# Usage: pyinstaller build/mac.spec

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
)

app = BUNDLE(
    exe,
    name='Watermark.app',
    icon=None,
    bundle_identifier='com.watermark.app',
    info_plist={
        'NSHighResolutionCapable': True,
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'CFBundleName': 'Watermark',
        'LSUIElement': False,
    },
)
