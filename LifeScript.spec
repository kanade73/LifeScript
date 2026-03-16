# -*- mode: python ; coding: utf-8 -*-
import os
import importlib

block_cipher = None

# Flet desktop のパスを取得
flet_desktop_path = os.path.dirname(importlib.import_module("flet_desktop").__file__)
litellm_path = os.path.dirname(importlib.import_module("litellm").__file__)
certifi_path = os.path.dirname(importlib.import_module("certifi").__file__)

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('lifescript', 'lifescript'),
        ('.env', '.'),
        # Flet desktop (Fletの内部ブラウザ)
        (flet_desktop_path, 'flet_desktop'),
        # litellm 全体（データファイル+サブモジュール）
        (litellm_path, 'litellm'),
        # certifi CA証明書
        (os.path.join(certifi_path, 'cacert.pem'), 'certifi'),
    ],
    hiddenimports=[
        'lifescript',
        'lifescript.ui.app',
        'lifescript.ui.splash_screen',
        'lifescript.ui.login_screen',
        'lifescript.ui.main_screen',
        'lifescript.ui.home_view',
        'lifescript.ui.dashboard_view',
        'lifescript.ui.concierge_view',
        'lifescript.ui.onboarding_screen',
        'lifescript.compiler.compiler',
        'lifescript.scheduler.scheduler',
        'lifescript.database.client',
        'lifescript.sandbox.runner',
        'lifescript.functions',
        'lifescript.functions.notify',
        'lifescript.functions.calendar_funcs',
        'lifescript.functions.machine',
        'lifescript.chat',
        'lifescript.context_analyzer',
        'lifescript.traits',
        'lifescript.log_queue',
        'lifescript.api',
        'lifescript.exceptions',
        'apscheduler',
        'apscheduler.schedulers.background',
        'apscheduler.triggers.interval',
        'apscheduler.triggers.cron',
        'litellm',
        'RestrictedPython',
        'supabase',
        'gotrue',
        'httpx',
        'httpcore',
        'h11',
        'anyio',
        'sniffio',
        'dotenv',
        'certifi',
        'flet',
        'flet_desktop',
        'flet.controls',
        'flet.canvas',
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
    [],
    exclude_binaries=True,
    name='LifeScript',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
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
    upx=False,
    upx_exclude=[],
    name='LifeScript',
)

app = BUNDLE(
    coll,
    name='LifeScript.app',
    icon='LifeScript.icns',
    bundle_identifier='com.lifescript.app',
    info_plist={
        'CFBundleName': 'LifeScript',
        'CFBundleDisplayName': 'LifeScript',
        'CFBundleVersion': '0.2.0',
        'CFBundleShortVersionString': '0.2.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '13.0',
    },
)
