"""应用日志管理模块。"""

from __future__ import annotations

import logging
from pathlib import Path

from utils.paths import get_log_dir


def get_logger(name: str) -> logging.Logger:
    """获取统一配置的日志器。

    功能描述：
        为指定模块创建日志器，输出到控制台与 `logs/app.log`。

    参数说明：
        name (str): 日志器名称，通常为模块路径。

    返回值说明：
        logging.Logger: 已配置完成的日志器对象。

    异常说明：
        ValueError: 当 `name` 为空字符串时抛出。
        OSError: 当日志目录或日志文件创建失败时抛出。
    """

    if name.strip() == "":
        raise ValueError("日志名称不能为空")

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    log_dir: Path = get_log_dir()
    log_file = log_dir / "app.log"

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger
