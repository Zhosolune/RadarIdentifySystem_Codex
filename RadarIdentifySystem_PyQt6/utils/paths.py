"""路径工具模块。"""

from __future__ import annotations

from pathlib import Path


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
        确保 `config` 目录存在并返回目录路径。

    参数说明：
        无。

    返回值说明：
        Path: 配置目录路径。

    异常说明：
        OSError: 当配置目录创建失败时抛出。
    """

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


def get_log_dir() -> Path:
    """获取日志目录。

    功能描述：
        确保 `logs` 目录存在并返回目录路径。

    参数说明：
        无。

    返回值说明：
        Path: 日志目录路径。

    异常说明：
        OSError: 当日志目录创建失败时抛出。
    """

    log_dir = get_project_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir
