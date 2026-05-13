# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_all, collect_submodules
import glob

block_cipher = None

# Proje kök dizini
project_root = os.path.abspath('.')

# Kütüphane yollarını manuel bulalım (Hook'lar bazen yetersiz kalabiliyor)
import sv_ttk
import PIL
sv_ttk_path = os.path.dirname(sv_ttk.__file__)
pil_path = os.path.dirname(PIL.__file__)

added_files = [
    ('settings.py', '.'),
    ('arduino.py', '.'),
    ('effects.py', '.'),
    ('game_data.db', '.'),
    # sv_ttk temalarını doğrudan ekle
    (os.path.join(sv_ttk_path, 'theme'), 'sv_ttk/theme'),
]

# PIL alt modüllerini ve verilerini topla
datas_pil, binaries_pil, hidden_pil = collect_all('PIL')
added_files += datas_pil

# Kritik: _imagingtk modülünü manuel bulup ekle
pil_binaries = binaries_pil
for pyd in glob.glob(os.path.join(pil_path, "_imagingtk*")):
    pil_binaries.append((pyd, 'PIL'))

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=pil_binaries,
    datas=added_files,
    hiddenimports=['pygame', 'pygame_ce', 'serial', 'sqlite3', 'numpy', 'tkinter', '_tkinter', 'PIL', 'PIL.Image', 'PIL.ImageTk', 'PIL._imagingtk'] + hidden_pil,
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
    console=True, # Konsol penceresini göster (hata ayıklama için)
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
