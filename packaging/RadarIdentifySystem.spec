# -*- mode: python ; coding: utf-8 -*-
"""RadarIdentifySystem 的 PyInstaller onedir 构建配置。"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules


ROOT = Path(SPECPATH).resolve().parent
ICON_FILE = ROOT / "build" / "packaging" / "icon.ico"
VERSION_FILE = ROOT / "packaging" / "RadarIdentifySystem.version.txt"
ONNXRUNTIME_HOOK = ROOT / "packaging" / "runtime_hooks" / "preload_onnxruntime.py"

analysis = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=collect_dynamic_libs("onnxruntime"),
    datas=[(str(ROOT / "resources"), "resources")],
    hiddenimports=collect_submodules("openpyxl"),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ONNXRUNTIME_HOOK)],
    excludes=["PyQt5", "PySide6", "pytest"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="RadarIdentifySystem",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_FILE),
    version=str(VERSION_FILE),
    contents_directory="_internal",
)

bundle = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="RadarIdentifySystem",
)
