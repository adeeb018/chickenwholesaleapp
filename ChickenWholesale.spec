# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

a = Analysis(
    ['app/main.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'sqlalchemy.ext.baked',
        'sqlalchemy.sql.default_comparator',
        'sqlalchemy.dialects.sqlite',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtPrintSupport',
        'sqlite3',
        'decimal',
        'datetime',
        'app',
        'app.config',
        'app.config.settings',
        'app.database',
        'app.database.models',
        'app.database.connection',
        'app.database.base',
        'app.database.repositories',
        'app.domain',
        'app.domain.models',
        'app.domain.accounting',
        'app.domain.weight_loss',
        'app.services',
        'app.ui',
        'app.ui.main_window',
        'app.ui.styles',
        'app.ui.styles.theme',
        'app.ui.components',
        'app.ui.views',
        'app.utils',
        'app.utils.date_utils',
        'app.utils.decimal_utils'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'IPython',
        'unittest',
        'pytest'
    ],
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
    name='ChickenWholesale',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ChickenWholesale'
)
