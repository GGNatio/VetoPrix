# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Python + PyQt6 + matplotlib embarqués."""
import sys
from PyInstaller.utils.hooks import collect_all

datas = [
    ("VERSION", "."),
    ("tarifs", "tarifs"),
]
binaries = []
hiddenimports = ["app.update.apply"]

for pkg in ("PyQt6", "matplotlib"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name="VetoPrix",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # pas de fenêtre console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="VetoPrix",
)

# Bundle .app sur macOS uniquement
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="VetoPrix.app",
        icon=None,
        bundle_identifier="com.vetoprix.app",
        info_plist={
            "CFBundleName": "VetoPrix",
            "CFBundleDisplayName": "VetoPrix",
            "CFBundleShortVersionString": open("VERSION", encoding="utf-8").read().strip(),
            "NSHighResolutionCapable": True,
        },
    )
