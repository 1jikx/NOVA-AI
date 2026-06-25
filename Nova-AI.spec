# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for NOVA AI — Windows build
# Usage: pyinstaller Nova-AI.spec

import os, sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
base_dir = os.path.abspath('.')

a = Analysis(
    ['Nova-AI-Windows.py'],
    pathex=[base_dir],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('core', 'core'),
        ('memory', 'memory'),
    ],
    hiddenimports=[
        'actions.file_processor',
        'actions.flight_finder',
        'actions.open_app',
        'actions.weather_report',
        'actions.send_message',
        'actions.reminder',
        'actions.computer_settings',
        'actions.screen_processor',
        'actions.youtube_video',
        'actions.desktop',
        'actions.browser_control',
        'actions.file_controller',
        'actions.code_helper',
        'actions.dev_agent',
        'actions.web_search',
        'actions.computer_control',
        'actions.game_updater',
        'agent.task_queue',
        'agent.executor',
        'agent.planner',
        'agent.error_handler',
        'memory.memory_manager',
        'memory.config_manager',
        'core.llm_helper',
        'core.network',
        'numpy',
        'sounddevice',
        'google.genai',
        'google.generativeai',
        'pyautogui',
        'pyperclip',
        'cv2',
        'mss',
        'psutil',
        'send2trash',
        'duckduckgo_search',
        'bs4',
        'requests',
        'PIL',
        'youtube_transcript_api',
        'pptx',
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
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
    name='Nova-AI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    name='Nova-AI',
)
