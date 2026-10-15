# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_all

datas = [('hand_landmarker.task', '.')]
binaries = []
hiddenimports = []

for package in ('mediapipe', 'cv2', 'speech_recognition', 'pyaudio'):
    try:
        d, b, h = collect_all(package)
        datas += d
        binaries += b
        hiddenimports += h
    except (ImportError, ModuleNotFoundError):
        pass

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

if sys.platform == 'darwin':
    exe = EXE(
        pyz, a.scripts, [], exclude_binaries=True,
        name='KINETIX', debug=False,
        bootloader_ignore_signals=False, strip=False, upx=False,
        console=False, argv_emulation=False,
    )
    coll = COLLECT(
        exe, a.binaries, a.datas, strip=False, upx=False, name='KINETIX'
    )
    app = BUNDLE(
        coll, name='KINETIX.app',
        bundle_identifier='com.kinetix.englishgame',
        info_plist={
            'NSCameraUsageDescription': 'KINETIX utiliza la camara para detectar movimientos de la mano durante el juego y mostrar la vista previa en Ajustes.',
            'NSMicrophoneUsageDescription': 'KINETIX utiliza el microfono al mantener pulsado el boton de hablar con el Tutor IA.',
        },
    )
else:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name='KINETIX', debug=False,
        bootloader_ignore_signals=False, strip=False, upx=False,
        console=False, disable_windowed_traceback=False,
    )
