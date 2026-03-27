from pathlib import Path
import os
import sys
import PyInstaller.__main__


root_dir = Path(__file__).resolve().parent
spec_path = root_dir / "RadarIdentifySystem.spec"


if __name__ == "__main__":
    os.chdir(root_dir)
    sys.path.insert(0, str(root_dir))
    if not spec_path.exists():
        raise FileNotFoundError(f"Spec 文件不存在: {spec_path}")
    workpath = root_dir / "build"
    distpath = root_dir / "dist"
    PyInstaller.__main__.run(
        [
            "--noconfirm",
            "--clean",
            "--log-level=WARN",
            f"--workpath={workpath}",
            f"--distpath={distpath}",
            str(spec_path),
        ]
    )
