"""应用日志管理模块。"""

from __future__ import annotations

from datetime import datetime
import logging
import os
from pathlib import Path
from typing import Final
from typing import Optional


_DEFAULT_LOG_DIR: Final[Path] = Path.home() / ".RadarIdentifySystem" / "logs"
_RUN_TIMESTAMP: Final[str] = datetime.now().strftime("%y%m%d_%H%M%S")
_RUN_LOG_FILE_NAME: Final[str] = f"RadarIdentifySystem_run_{_RUN_TIMESTAMP}.log"
_CURRENT_LOG_FILE_PATH: Optional[Path] = None
_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)


def _build_module_path(file_path: str) -> str:
    """构建点分模块路径。

    功能描述：
        将日志记录的绝对文件路径转换为“项目根相对路径 + 点分连接”的显示格式，
        并移除 `.py` 后缀。

    参数说明：
        file_path (str): 日志记录中的源文件绝对路径。

    返回值说明：
        str: 点分模块路径字符串。

    异常说明：
        无。
    """

    # 解析当前记录文件路径
    path = Path(file_path).resolve()
    try:
        # 计算项目根相对路径
        relative_path = path.relative_to(_PROJECT_ROOT)
    except ValueError:
        # 回退为文件名路径
        relative_path = Path(path.name)

    # 移除 .py 后缀并转为点分表示
    return ".".join(relative_path.with_suffix("").parts)


class RuntimeContextFilter(logging.Filter):
    """日志上下文补全过滤器。"""

    def filter(self, record: logging.LogRecord) -> bool:
        """补全日志上下文字段。

        功能描述：
            为每条日志补全 `session_id` 与 `module_path` 字段，避免格式化时报错，
            并统一文件路径显示格式。

        参数说明：
            record (logging.LogRecord): 原始日志记录对象。

        返回值说明：
            bool: 始终返回 True，表示允许输出。

        异常说明：
            无。
        """

        # 补全缺省会话标识
        if not hasattr(record, "session_id"):
            record.session_id = "-"
        # 写入点分文件路径
        record.module_path = _build_module_path(record.pathname)
        return True


def get_log_dir_path(log_dir: str | Path | None = None) -> Path:
    """解析并确保日志目录存在。

    功能描述：
        将外部传入的日志目录（或默认目录）标准化为绝对路径并确保目录存在。

    参数说明：
        log_dir (str | Path | None): 目标日志目录；当为 None 或空字符串时使用默认目录。

    返回值说明：
        Path: 标准化后的日志目录路径。

    异常说明：
        OSError: 当目录创建失败时抛出。
    """

    raw = str(log_dir).strip() if log_dir is not None else ""
    resolved = Path(raw).expanduser() if raw else _DEFAULT_LOG_DIR
    path = resolved.resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_run_log_file_path(log_dir: str | Path | None = None) -> Path:
    """构建当前进程的日志文件路径。

    功能描述：
        使用固定运行时间戳生成本次进程专属日志文件名。

    参数说明：
        log_dir (str | Path | None): 目标日志目录；为空时使用默认目录。

    返回值说明：
        Path: 当前进程日志文件路径。

    异常说明：
        OSError: 当目录创建失败时抛出。
    """

    return get_log_dir_path(log_dir) / _RUN_LOG_FILE_NAME


def configure_logging(log_dir: str | Path | None = None) -> Path:
    """初始化全局日志系统。

    功能描述：
        清理 root logger 的旧 handler，并重新挂载控制台和文件 handler。
        本函数应在程序启动阶段调用一次。

    参数说明：
        log_dir (str | Path | None): 日志目录；为空时使用默认目录。

    返回值说明：
        Path: 本次运行对应的日志文件路径。

    异常说明：
        OSError: 当日志文件创建失败时抛出。
    """

    global _CURRENT_LOG_FILE_PATH

    # 获取日志文件路径（内部会自动创建日志目录）
    log_file = build_run_log_file_path(log_dir)
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(session_id)s] [%(module_path)s] [%(funcName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    context_filter = RuntimeContextFilter()

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(context_filter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(context_filter)

    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)

    _CURRENT_LOG_FILE_PATH = log_file
    return log_file


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
    if _CURRENT_LOG_FILE_PATH is not None:
        return _CURRENT_LOG_FILE_PATH
    return build_run_log_file_path(None)


def clear_all_logs(log_dir: str | Path | None = None) -> int:
    """清理日志目录下的历史日志文件。

    功能描述：
        删除日志目录下匹配 `RadarIdentifySystem_run_*.log` 的日志文件。

    参数说明：
        log_dir (str | Path | None): 目标日志目录；为空时使用当前日志文件所在目录。

    返回值说明：
        int: 成功删除的日志文件数量。

    异常说明：
        无。
    """

    import glob

    target_log_dir = (
        get_current_log_file_path().parent
        if log_dir is None
        else get_log_dir_path(log_dir)
    )
    if not target_log_dir.exists():
        return 0

    count = 0
    pattern = str(target_log_dir / "RadarIdentifySystem_run_*.log")
    current_log_file = get_current_log_file_path().resolve()
    for log_file in glob.glob(pattern):
        try:
            if Path(log_file).resolve() == current_log_file:
                continue
            os.remove(log_file)
            count += 1
        except Exception as e:
            LOGGER.error("删除日志文件失败：%s，错误：%s", log_file, e, extra={"session_id": "-"})

    return count
