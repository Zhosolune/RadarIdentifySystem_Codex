"""应用日志管理模块。"""

from __future__ import annotations

from datetime import datetime
import logging
import os
from pathlib import Path
from typing import Final

from app.app_config import appConfig

def get_logger(name: str) -> logging.Logger:
    """获取统一配置的日志器。

    功能描述：
        为指定模块创建日志器，输出到控制台与本次启动对应的日志文件。

    参数说明：
        name (str): 日志器名称，通常为模块路径。

    返回值说明：
        logging.Logger: 已配置完成的日志器对象。

    异常说明：
        ValueError: 当 `name` 为空字符串时抛出。
        OSError: 当日志目录或日志文件创建失败时抛出。
    """

    # 防御式校验：日志器名称为空会导致后续定位日志来源困难。
    if name.strip() == "":
        raise ValueError("日志名称不能为空")

    logger = logging.getLogger(name)
    # 同名 logger 已初始化时直接复用，避免重复挂载 handler 造成重复输出。
    if logger.handlers:
        return logger

    # 当前进程固定写入同一个“启动日志文件”。
    log_file = get_current_log_file_path()

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    # 同时输出到控制台与文件，便于调试与落盘追踪。
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    # 关闭向上传播，避免被 root logger 再次打印。
    logger.propagate = False
    return logger


def get_log_dir_path() -> Path:
    """获取日志目录路径。

    功能描述：
        从配置项 `appConfig.logDir` 获取日志目录，确保目录存在并返回绝对路径。

    参数说明：
        无。

    返回值说明：
        Path: 日志目录绝对路径。

    异常说明：
        OSError: 当日志目录创建失败时抛出。
    """

    # 优先使用配置项中的日志目录。
    raw_log_dir = str(appConfig.logDir.value).strip()
    if raw_log_dir == "":
        # 配置为空时回退到用户目录下的默认日志目录。
        raw_log_dir = str(Path.home() / ".RadarIdentifySystem" / "logs")

    # 统一规范化路径并确保目录存在。
    log_dir = Path(raw_log_dir).expanduser().resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


# 进程级启动时间戳：保证“每次启动一个日志文件”。
_RUN_TIMESTAMP: Final[str] = datetime.now().strftime("%y%m%d_%H%M%S")
_RUN_LOG_FILE_NAME: Final[str] = f"RadarIdentifySystem_run_{_RUN_TIMESTAMP}.log"


def get_current_log_file_path() -> Path:
    """获取当前进程日志文件路径。

    功能描述：
        基于进程启动时刻生成固定日志文件名，确保同一次运行写入同一个日志文件。

    参数说明：
        无。

    返回值说明：
        Path: 当前进程对应的日志文件路径。

    异常说明：
        OSError: 当日志目录创建失败时抛出。
    """

    # 返回当前运行实例唯一日志文件路径。
    return get_log_dir_path() / _RUN_LOG_FILE_NAME


LOGGER = get_logger("app.logger")


def clear_all_logs() -> int:
    """清理日志目录下的历史日志文件。

    功能描述：
        删除日志目录下匹配 `RadarIdentifySystem_run_*.log` 的日志文件。

    参数说明：
        无。

    返回值说明：
        int: 成功删除的日志文件数量。

    异常说明：
        无。
    """

    import glob

    log_dir = get_log_dir_path()
    if not log_dir.exists():
        return 0

    count = 0
    # 仅匹配本系统约定命名的运行日志文件。
    pattern = str(log_dir / "RadarIdentifySystem_run_*.log")
    current_log_file = get_current_log_file_path().resolve()
    for log_file in glob.glob(pattern):
        try:
            # 跳过当前运行日志，避免清理时误删正在写入的文件。
            if Path(log_file).resolve() == current_log_file:
                continue
            os.remove(log_file)
            count += 1
        except Exception as e:
            LOGGER.error("删除日志文件失败：%s，错误：%s", log_file, e)

    return count
