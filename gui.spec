# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the PySide6 desktop GUI binary.
# Run from the repository root: pyinstaller gui.spec
#
# Notes:
#   - console=False → no terminal window on Windows/macOS.
#   - datas includes server/templates so the embedded Flask server can render
#     the dashboard and the /config device-configuration page.
#   - config.json and device_config.json are NOT bundled:
#       config.json     - external; place next to the binary before first use.
#       device_config.json - created automatically at runtime via external_path.
#   - If the binary fails at startup with "This application failed to start
#     because no Qt platform plugin could be initialized", uncomment the
#     collect_all('PySide6') line below and rebuild.

# from PyInstaller.utils.hooks import collect_all
# pyside6_datas, pyside6_binaries, pyside6_hidden = collect_all('PySide6')

a = Analysis(
    ['server/gui.py'],
    pathex=['server'],
    binaries=[],
    datas=[
        ('server/templates', 'templates'),
    ],
    hiddenimports=[
        'serial.tools.list_ports',   # used by gui.py for port discovery
        'werkzeug.serving',           # make_server - not always auto-detected
    ],
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
    name='BodyTempMonitor-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # GUI-приложение: без терминального окна
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
