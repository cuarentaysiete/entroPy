# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for the entroPy desktop application.

Build (on macOS, from the repository root):

    pip install -e . pyinstaller
    pyinstaller entroPy.spec

Produces dist/entroPy/entroPy.app (double-clickable, no Python required).
The external signature table is bundled next to core.py so runtime
identification keeps full coverage; if it were ever missing, core.py
transparently falls back to the embedded table.
"""

block_cipher = None

a = Analysis(
    ['gui.py'],
    pathex=['.'],
    binaries=[],
    datas=[('magic_signatures.json', '.')],
    hiddenimports=['pyqtgraph'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    no_archive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='entroPy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # windowed app: no terminal window
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='entroPy',
)
