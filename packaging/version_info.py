"""从项目元数据生成 PyInstaller 使用的 Windows 版本资源。"""

from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path


_RELEASE_VERSION_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:\.(0|[1-9]\d*))?$"
)


def generate_version_resource(project_file: Path, output_file: Path) -> str:
    """读取项目版本并写入 Windows 可执行文件版本资源。

    仅接受三段或四段纯数字版本，确保同一版本能同时用于
    ``pyproject.toml``、Windows 文件属性和 Inno Setup。

    Args:
        project_file [Path]: 包含 ``[project].version`` 的 pyproject.toml 路径。
        output_file [Path]: 待生成的 PyInstaller 版本资源文件路径。

    Returns:
        str: 从项目元数据读取到的原始发布版本。

    Raises:
        FileNotFoundError: 项目元数据文件不存在。
        KeyError: 项目元数据缺少 ``[project].version``。
        ValueError: 版本不是三段或四段纯数字格式。
        OSError: 无法读取项目文件或写入版本资源。
    """
    with project_file.open("rb") as file:
        project = tomllib.load(file)

    # 发布版本同时进入 Python 元数据、PE 文件属性和安装器，先限制为三/四段数字。
    version = project["project"]["version"]
    if not isinstance(version, str):
        raise ValueError("[project].version 必须是字符串")

    match = _RELEASE_VERSION_PATTERN.fullmatch(version)
    if match is None:
        raise ValueError(
            "[project].version 必须使用三段或四段纯数字格式，例如 0.1.0"
        )

    version_parts = [int(value) for value in match.groups(default="0")]
    fixed_version = ", ".join(str(value) for value in version_parts)
    # PyInstaller 读取文本形式的 VSVersionInfo，第四段缺失时固定补零。
    resource_text = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({fixed_version}),
    prodvers=({fixed_version}),
    mask=0x3F,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '080404B0',
        [
          StringStruct('CompanyName', 'RadarIdentifySystem'),
          StringStruct('FileDescription', '雷达信号识别系统'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', 'RadarIdentifySystem'),
          StringStruct('OriginalFilename', 'RadarIdentifySystem.exe'),
          StringStruct('ProductName', 'RadarIdentifySystem'),
          StringStruct('ProductVersion', '{version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(resource_text, encoding="utf-8", newline="\n")
    return version


def main() -> int:
    """解析命令行参数并生成版本资源。

    Returns:
        int: 成功时返回 0；参数或版本错误由命令行进程报告。

    Raises:
        FileNotFoundError: 项目元数据文件不存在。
        KeyError: 项目元数据缺少 ``[project].version``。
        ValueError: 项目版本格式不受支持。
        OSError: 版本资源无法写入。
    """
    parser = argparse.ArgumentParser(description="生成 Windows EXE 版本资源")
    parser.add_argument("--project-file", type=Path, required=True)
    parser.add_argument("--output-file", type=Path, required=True)
    arguments = parser.parse_args()
    # 标准输出只写版本号，供 PowerShell 继续传递给 Inno Setup。
    version = generate_version_resource(
        project_file=arguments.project_file,
        output_file=arguments.output_file,
    )
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
