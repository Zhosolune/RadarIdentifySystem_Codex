import ctypes
import os
import sys
from pathlib import Path


def _log(message: str) -> None:
    """输出自检日志"""
    stream = sys.stderr if sys.stderr is not None else sys.stdout
    if stream is None:
        return
    stream.write(message + os.linesep)


def _get_base_dir() -> Path:
    """获取运行时基准目录"""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path.cwd()


def _check_dlls(dll_dir: Path, dll_names: list[str]) -> None:
    """检测 DLL 是否可加载"""
    for dll_name in dll_names:
        dll_path = dll_dir / dll_name
        if not dll_path.exists():
            _log(f"[DLL-CHECK] missing: {dll_path}")
            continue
        try:
            ctypes.CDLL(str(dll_path))
            _log(f"[DLL-CHECK] loaded: {dll_path}")
        except OSError as exc:
            _log(f"[DLL-CHECK] load failed: {dll_path} ({exc})")


base_dir = _get_base_dir()
onnx_capi_dir = base_dir / "onnxruntime" / "capi"
if onnx_capi_dir.is_dir():
    _check_dlls(
        onnx_capi_dir,
        [
            "onnxruntime.dll",
            "onnxruntime_providers_shared.dll",
            "onnxruntime_providers_cpu.dll",
            "onnxruntime_pybind11_state.pyd",
        ],
    )
