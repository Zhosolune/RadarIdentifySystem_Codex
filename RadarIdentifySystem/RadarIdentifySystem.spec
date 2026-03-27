# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs
import importlib.util
from pathlib import Path

block_cipher = None

# ==========================================================
# 核心修复逻辑：使用 collect_all 收集 onnxruntime 的所有组件
# ==========================================================
project_root = Path.cwd().resolve()

def _get_onnxruntime_capi_dir() -> Path:
    """获取 onnxruntime/capi 目录"""
    spec = importlib.util.find_spec("onnxruntime")
    if not spec or not spec.origin:
        return Path()
    return Path(spec.origin).parent / "capi"

datas, binaries, hiddenimports = collect_all('onnxruntime')
binaries += collect_dynamic_libs('onnxruntime')
onnx_capi_dir = _get_onnxruntime_capi_dir()
if onnx_capi_dir.is_dir():
    capi_dlls = [
        "onnxruntime.dll",
        "onnxruntime_providers_shared.dll",
        "onnxruntime_providers_cpu.dll",
    ]
    for dll_name in capi_dlls:
        dll_path = onnx_capi_dir / dll_name
        if dll_path.exists():
            binaries.append((str(dll_path), "onnxruntime/capi"))

# 添加其他隐式导入
hiddenimports += [
    'onnxruntime.capi',
    'onnxruntime.capi.onnxruntime_pybind11_state',
    'sklearn.utils._cython_blas', 
    'scipy.special.cython_special'
]

# 添加项目资源文件
# (源路径, 目标路径)
project_datas = [
    ('resources', 'resources'),
    ('config', 'config'),
    ('model_wm', 'model_wm'),
]

# 将项目资源合并到 collect_all 的结果中
datas += project_datas

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[
        'runtime_hooks/onnxruntime_dll_dir.py',
        'runtime_hooks/dll_self_check.py',
    ],
    excludes=['test', 'tests', 'docs', '.trae'],
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
    name='RadarIdentifySystem',
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
    icon='resources\\icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[
        'onnxruntime.dll',
        'onnxruntime_providers_shared.dll',
        'onnxruntime_providers_cpu.dll',
        'onnxruntime_pybind11_state.pyd',
    ],
    name='RadarIdentifySystem',
)
