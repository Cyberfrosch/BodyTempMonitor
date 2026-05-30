# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Flask HTTP server binary.
# Run from the repository root: pyinstaller server.spec

a = Analysis(
    ['server/server.py'],
    pathex=['server'],
    binaries=[],
    datas=[('server/templates', 'templates')],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='BodyTempMonitor-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
