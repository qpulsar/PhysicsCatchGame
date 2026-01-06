# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# Proje kök dizini
project_root = os.path.abspath('.')

added_files = [
    ('assets', 'assets'),
    ('game_data.db', '.'),
    ('settings.py', '.'),
    ('arduino.py', '.'),
    ('effects.py', '.'),
]

# sv-ttk verilerini topla
added_files += collect_data_files('sv_ttk')

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=[],
    datas=added_files,
    hiddenimports=['pygame', 'serial', 'PIL', 'sv_ttk', 'sqlite3'],
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
    name='PhysicsCatchGame',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # Konsol penceresini gizle
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/images/icon.ico' if os.path.exists('assets/images/icon.ico') else None
)

app = BUNDLE(
    exe,
    name='PhysicsCatchGame.app',
    icon='assets/images/icon.icns' if os.path.exists('assets/images/icon.icns') else None,
    bundle_identifier='com.physicsgame.catch',
)
