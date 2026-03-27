import os
import sys
from pathlib import Path


if getattr(sys, "frozen", False):
    base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    capi_dir = base_dir / "onnxruntime" / "capi"
    if capi_dir.is_dir():
        os.add_dll_directory(str(capi_dir))
