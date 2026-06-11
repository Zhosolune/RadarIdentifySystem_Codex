"""路径工具模块。"""

from __future__ import annotations

from pathlib import Path
import sys


def is_packaged_runtime() -> bool:
    """判断当前是否为打包后的运行环境。

    Args:
        无。

    Returns:
        True 表示 PyInstaller 等打包环境，False 表示源码调试环境。

    Raises:
        无显式抛出异常。

    Example:
        >>> isinstance(is_packaged_runtime(), bool)
        True
    """

    return bool(getattr(sys, "frozen", False))


def get_project_root() -> Path:
    """获取项目根目录。

    功能描述：
        返回当前项目 `RadarIdentifySystem_PyQt6` 的绝对路径。

    参数说明：
        无。

    返回值说明：
        Path: 项目根目录路径。

    异常说明：
        RuntimeError: 当推导出的目录不存在时抛出。
    """

    root = Path(__file__).resolve().parent.parent
    if not root.exists():
        raise RuntimeError("项目根目录不存在")
    return root


def get_config_dir() -> Path:
    """获取配置目录。

    功能描述：
        源码调试环境返回项目内 `config` 目录；打包运行环境返回
        `Path.home() / ".RadarIdentifySystem" / "config"`。

    参数说明：
        无。

    返回值说明：
        Path: 配置目录路径。

    异常说明：
        OSError: 当配置目录创建失败时抛出。
    """

    if is_packaged_runtime():
        config_dir = Path.home() / ".RadarIdentifySystem" / "config"
    else:
        config_dir = get_project_root() / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file_path() -> Path:
    """获取配置文件路径。

    功能描述：
        返回固定配置文件 `config/config.json` 的路径。

    参数说明：
        无。

    返回值说明：
        Path: 配置文件路径。

    异常说明：
        OSError: 当配置目录创建失败时抛出。
    """

    return get_config_dir() / "config.json"


def get_import_file_list_path() -> Path:
    """获取导入文件列表状态文件路径。

    功能描述：
        源码调试环境返回项目内 `config/import_file_list.json`；
        打包运行环境返回用户目录下的 `.RadarIdentifySystem/config/import_file_list.json`。

    Args:
        无。

    Returns:
        Path: 导入文件列表状态 JSON 文件路径。

    Raises:
        OSError: 当配置目录创建失败时抛出。

    Example:
        >>> get_import_file_list_path().name
        'import_file_list.json'
    """

    return get_config_dir() / "import_file_list.json"


def get_log_dir() -> Path:
    """获取日志目录。

    功能描述：
        源码调试环境返回项目内 `logs` 目录；打包运行环境返回
        `Path.home() / ".RadarIdentifySystem" / "logs"`。

    参数说明：
        无。

    返回值说明：
        Path: 日志目录路径。

    异常说明：
        OSError: 当日志目录创建失败时抛出。
    """

    if is_packaged_runtime():
        log_dir = Path.home() / ".RadarIdentifySystem" / "logs"
    else:
        log_dir = get_project_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir
