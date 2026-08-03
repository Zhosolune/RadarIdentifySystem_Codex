"""应用日志管理模块。"""

from __future__ import annotations

from contextvars import ContextVar, Token
from datetime import datetime
import logging
import os
from pathlib import Path
import re
from typing import Final, Optional

from utils.paths import get_log_dir


_DEFAULT_LOG_DIR: Final[Path] = get_log_dir()
_RUN_TIMESTAMP: Final[str] = datetime.now().strftime("%y%m%d_%H%M%S")
_RUN_LOG_FILE_NAME: Final[str] = f"RadarIdentifySystem_run_{_RUN_TIMESTAMP}.log"
_SESSION_LOG_DIR_NAME: Final[str] = "sessions"
_SESSION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_-]+$")
_CURRENT_LOG_FILE_PATH: Optional[Path] = None
_SESSION_LOG_HANDLER: Optional["SessionRoutingHandler"] = None
_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)
LOG_LEVELS: Final[dict[str, int]] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
}

# 对外只展示约定的四级名称，避免同一等级同时出现 WARNING/WARN。
logging.addLevelName(logging.WARNING, "WARN")

# 会话日志上下文：承载“当前 session_id”，供 Filter 兜底读取。
# Worker 在 run() 开头 bind、结束 unbind，下层 core/infra 模块无需传参即可自动带上 id。
_session_id_ctx: ContextVar[str] = ContextVar("session_id", default="-")


def bind_session_log_context(session_id: str) -> Token[str]:
    """绑定当前线程/协程的会话日志标识。

    在后台线程入口（如 Worker.run()）调用，将 session_id 写入
    contextvar，使该线程内所有未显式传 extra 的日志自动归属该 session。
    返回的 Token 必须在作用域结束时传给 unbind_session_log_context 复位。

    Args:
        session_id (str): 当前会话标识，不应为空字符串。

    Returns:
        contextvar 复位令牌，供 unbind_session_log_context 使用。

    Raises:
        无显式抛出异常。

    Example:
        >>> token = bind_session_log_context("SESSION_A")
        >>> unbind_session_log_context(token)
    """
    return _session_id_ctx.set(session_id)


def unbind_session_log_context(token: Token[str]) -> None:
    """复位会话日志标识。

    将 contextvar 恢复到 bind 前的状态，防止 session_id 泄漏到
    后续无关日志（如线程池线程复用场景）。

    Args:
        token (Token[str]): bind_session_log_context 返回的复位令牌。

    Returns:
        None: 无返回值。

    Raises:
        ValueError: 当 token 不属于当前 context 时抛出。

    Example:
        >>> token = bind_session_log_context("SESSION_A")
        >>> unbind_session_log_context(token)
    """
    _session_id_ctx.reset(token)


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
    """日志上下文补全过滤器。

    负责为日志记录补齐 session_id 与 module_path 字段，避免 formatter
    在调用方未传入 extra 时出现字段缺失。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """补全日志上下文字段。

        为每条日志补全 `session_id` 与 `module_path` 字段，避免格式化时报错，
        并统一文件路径显示格式。session_id 取值优先级为显式 extra、当前线程
        的会话日志上下文、默认值 "-"。

        Args:
            record (logging.LogRecord): 原始日志记录对象，可能尚未包含 session_id 字段。

        Returns:
            始终返回 True，表示允许输出该条日志。

        Raises:
            无显式抛出异常。

        Example:
            >>> import logging
            >>> record = logging.LogRecord("demo", logging.INFO, __file__, 1, "msg", None, None)
            >>> RuntimeContextFilter().filter(record)
            True
            >>> hasattr(record, "session_id")
            True
        """

        # 补全缺省会话标识：显式 extra 优先，contextvar 兜底
        if not hasattr(record, "session_id"):
            record.session_id = _session_id_ctx.get()
        # 写入点分文件路径
        record.module_path = _build_module_path(record.pathname)
        return True


class SessionRoutingHandler(logging.Handler):
    """把已注册 Session 的日志复制到独立文件。

    Handler 只接受显式注册的 Session ID，避免把导入阶段暂存在
    ``session_id`` 字段中的数据包 ID 误当作 Session。日志文件在第一条匹配
    记录到达时按需创建，内部文件 Handler 的访问由父 Handler 锁串行保护。

    Attributes:
        log_dir [Path]: 当前运行日志根目录。
        formatter [logging.Formatter]: Session 文件使用的统一格式器。
    """

    def __init__(
        self,
        log_dir: str | Path,
        formatter: logging.Formatter,
    ) -> None:
        """初始化 Session 日志路由器。

        Args:
            log_dir [str | Path]: 当前运行日志根目录。
            formatter [logging.Formatter]: Session 文件使用的日志格式器。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 日志根目录无法创建时抛出。
        """
        super().__init__(level=logging.NOTSET)
        self.log_dir = get_log_dir_path(log_dir)
        self.formatter = formatter
        self._registered_session_ids: set[str] = set()
        self._file_handlers: dict[str, logging.FileHandler] = {}

    def register_session(self, session_id: str) -> Path:
        """注册需要独立落盘的 Session。

        注册操作幂等，不会立即打开文件；首条对应日志到达时才创建文件。

        Args:
            session_id [str]: 已持久化注册的 Session 唯一标识。

        Returns:
            Path: 当前运行中该 Session 对应的日志文件路径。

        Raises:
            ValueError: Session ID 为空或包含不安全文件名字符时抛出。
            OSError: Session 日志根目录无法访问时抛出。
        """
        safe_session_id = _validate_log_session_id(session_id)
        self.acquire()
        try:
            self._registered_session_ids.add(safe_session_id)
        finally:
            self.release()
        return build_session_log_file_path(
            safe_session_id,
            self.log_dir,
        )

    def unregister_session(self, session_id: str) -> None:
        """注销 Session 并关闭其独立日志文件。

        Args:
            session_id [str]: 需要结束文件路由的 Session 唯一标识。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: Session ID 为空或包含不安全文件名字符时抛出。
            OSError: 已打开的 Session 日志文件无法关闭时抛出。
        """
        safe_session_id = _validate_log_session_id(session_id)
        self.acquire()
        try:
            self._registered_session_ids.discard(safe_session_id)
            handler = self._file_handlers.pop(safe_session_id, None)
            if handler is not None:
                handler.close()
        finally:
            self.release()

    def current_log_paths(self) -> set[Path]:
        """返回当前已经打开的全部 Session 日志路径。

        Returns:
            set[Path]: 当前运行中已实际打开的 Session 日志绝对路径集合。

        Raises:
            OSError: Session 日志文件路径无法解析时抛出。
        """
        self.acquire()
        try:
            return {
                Path(handler.baseFilename).resolve()
                for handler in self._file_handlers.values()
            }
        finally:
            self.release()

    def emit(self, record: logging.LogRecord) -> None:
        """按日志记录中的 Session ID 路由到独立文件。

        Args:
            record [logging.LogRecord]: 已由上下文过滤器补齐字段的日志记录。

        Returns:
            None: 无返回值。

        Raises:
            无。文件写入异常交由 logging 的 ``handleError`` 处理。
        """
        session_id = getattr(record, "session_id", "-")
        if (
            not isinstance(session_id, str)
            or session_id not in self._registered_session_ids
        ):
            return
        try:
            handler = self._file_handlers.get(session_id)
            if handler is None:
                log_file = build_session_log_file_path(
                    session_id,
                    self.log_dir,
                )
                log_file.parent.mkdir(parents=True, exist_ok=True)
                handler = logging.FileHandler(
                    log_file,
                    encoding="utf-8",
                    delay=True,
                )
                handler.setFormatter(self.formatter)
                self._file_handlers[session_id] = handler
            handler.emit(record)
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        """关闭所有 Session 文件并释放 Handler。

        Returns:
            None: 无返回值。

        Raises:
            OSError: Session 日志文件无法关闭时抛出。
        """
        self.acquire()
        try:
            handlers = list(self._file_handlers.values())
            self._file_handlers.clear()
            self._registered_session_ids.clear()
            for handler in handlers:
                handler.close()
        finally:
            self.release()
        super().close()


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


def _validate_log_session_id(session_id: str) -> str:
    """校验 Session ID 可安全用作日志目录和文件名。"""
    if (
        not isinstance(session_id, str)
        or not session_id
        or _SESSION_ID_PATTERN.fullmatch(session_id) is None
    ):
        raise ValueError("session_id 只能包含字母、数字、下划线和连字符")
    return session_id


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


def build_session_log_file_path(
    session_id: str,
    log_dir: str | Path | None = None,
) -> Path:
    """构建当前进程中指定 Session 的独立日志路径。

    Args:
        session_id [str]: 已注册 Session 的安全唯一标识。
        log_dir [str | Path | None]: 日志根目录；为空时使用默认目录。

    Returns:
        Path: ``sessions/<session_id>`` 目录下的当前运行日志路径。

    Raises:
        ValueError: Session ID 为空或包含不安全文件名字符时抛出。
        OSError: Session 日志根目录无法访问时抛出。
        OSError: 日志根目录无法创建时抛出。

    Example:
        >>> path = build_session_log_file_path("SESSION_A")
        >>> path.parent.name
        'SESSION_A'
    """
    safe_session_id = _validate_log_session_id(session_id)
    file_name = (
        f"RadarIdentifySystem_session_{safe_session_id}_"
        f"{_RUN_TIMESTAMP}.log"
    )
    return (
        get_log_dir_path(log_dir)
        / _SESSION_LOG_DIR_NAME
        / safe_session_id
        / file_name
    )


def configure_logging(
    log_dir: str | Path | None = None,
    log_level: str = "INFO",
) -> Path:
    """初始化全局日志系统。

    功能描述：
        关闭 root logger 的旧 handler，并重新挂载控制台、全局运行文件和
        Session 路由 handler。本函数应在程序启动阶段调用一次。

    Args:
        log_dir [str | Path | None]: 日志目录；为空时使用默认目录。
        log_level [str]: 最低记录等级，支持 DEBUG、INFO、WARN、ERROR。

    Returns:
        Path: 本次运行对应的日志文件路径。

    Raises:
        OSError: 当日志文件创建失败时抛出。
        ValueError: 日志等级不受支持时抛出。
    """

    global _CURRENT_LOG_FILE_PATH, _SESSION_LOG_HANDLER

    # 获取日志文件路径（内部会自动创建日志目录）
    log_file = build_run_log_file_path(log_dir)
    formatter = logging.Formatter(
        # fmt="[%(asctime)s] [%(levelname)s] [%(session_id)s] [%(module_path)s] [%(funcName)s] %(message)s",
        fmt="[%(asctime)s][%(levelname)s][%(session_id)s][%(module_path)s][%(funcName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    context_filter = RuntimeContextFilter()

    normalized_level = _normalize_log_level(log_level)
    root_logger = logging.getLogger()
    root_logger.setLevel(normalized_level)
    # 先关闭旧 Handler，避免 Windows 下日志文件仍被占用。
    for old_handler in list(root_logger.handlers):
        root_logger.removeHandler(old_handler)
        old_handler.close()

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(normalized_level)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(context_filter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(normalized_level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(context_filter)

    session_handler = SessionRoutingHandler(log_file.parent, formatter)
    session_handler.setLevel(normalized_level)
    session_handler.addFilter(context_filter)

    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(session_handler)

    _CURRENT_LOG_FILE_PATH = log_file
    _SESSION_LOG_HANDLER = session_handler
    return log_file


def _normalize_log_level(log_level: str) -> int:
    """把四级日志名称转换为 logging 数值等级。"""
    normalized_name = str(log_level).strip().upper()
    try:
        return LOG_LEVELS[normalized_name]
    except KeyError as error:
        raise ValueError(f"不支持的日志等级: {log_level}") from error


def set_log_level(log_level: str) -> None:
    """立即更新全局与 Session 日志的最低记录等级。

    Args:
        log_level [str]: 最低记录等级，支持 DEBUG、INFO、WARN、ERROR。

    Returns:
        None: 无返回值。

    Raises:
        ValueError: 日志等级不受支持时抛出。

    Example:
        >>> set_log_level("WARN")
        >>> logging.getLogger().level == logging.WARNING
        True
    """
    normalized_level = _normalize_log_level(log_level)
    root_logger = logging.getLogger()
    root_logger.setLevel(normalized_level)
    # Handler 同步设置阈值，确保显式设置等级的第三方 logger 也不能绕过筛选。
    for handler in root_logger.handlers:
        handler.setLevel(normalized_level)


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


def register_session_log(session_id: str) -> Path | None:
    """为已注册 Session 启用独立日志路由。

    日志系统尚未初始化时保持无副作用，便于无 GUI 的模型和注册表测试使用。

    Args:
        session_id [str]: 已成功注册或恢复的 Session 唯一标识。

    Returns:
        Path | None: 日志系统已初始化时返回目标文件路径，否则返回 None。

    Raises:
        ValueError: Session ID 为空或包含不安全文件名字符时抛出。
        OSError: Session 日志根目录无法访问时抛出。
    """
    if _SESSION_LOG_HANDLER is None:
        return None
    return _SESSION_LOG_HANDLER.register_session(session_id)


def unregister_session_log(session_id: str) -> None:
    """停止指定 Session 的独立日志路由并关闭文件。

    Args:
        session_id [str]: 已删除或移出运行期注册表的 Session 唯一标识。

    Returns:
        None: 无返回值。

    Raises:
        ValueError: Session ID 为空或包含不安全文件名字符时抛出。
        OSError: 已打开的 Session 日志文件无法关闭时抛出。
    """
    if _SESSION_LOG_HANDLER is None:
        return
    _SESSION_LOG_HANDLER.unregister_session(session_id)


def shutdown_logging() -> None:
    """关闭当前应用安装的全部日志 Handler。

    Returns:
        None: 无返回值。

    Raises:
        OSError: 任一当前日志文件无法关闭时抛出。
    """
    global _SESSION_LOG_HANDLER

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()
    _SESSION_LOG_HANDLER = None


def clear_all_logs(log_dir: str | Path | None = None) -> int:
    """清理日志目录下的历史日志文件。

    功能描述：
        删除日志根目录中的历史运行日志及 ``sessions`` 子目录中的历史
        Session 日志。当前进程仍在使用的全局和 Session 文件会被保留。

    参数说明：
        log_dir (str | Path | None): 目标日志目录；为空时使用当前日志文件所在目录。

    返回值说明：
        int: 成功删除的日志文件数量。

    异常说明：
        OSError: 日志目录无法访问时抛出。
    """

    target_log_dir = (
        get_current_log_file_path().parent
        if log_dir is None
        else get_log_dir_path(log_dir)
    )
    if not target_log_dir.exists():
        return 0

    count = 0
    current_log_files = {get_current_log_file_path().resolve()}
    if _SESSION_LOG_HANDLER is not None:
        current_log_files.update(_SESSION_LOG_HANDLER.current_log_paths())
    candidates = list(
        target_log_dir.glob("RadarIdentifySystem_run_*.log")
    )
    candidates.extend(
        (
            target_log_dir / _SESSION_LOG_DIR_NAME
        ).glob("*/RadarIdentifySystem_session_*_*.log")
    )
    for log_file in candidates:
        try:
            if log_file.resolve() in current_log_files:
                continue
            os.remove(log_file)
            count += 1
        except Exception as e:
            LOGGER.error("删除日志文件失败：%s，错误：%s", log_file, e, extra={"session_id": "-"})

    _remove_empty_session_log_dirs(target_log_dir)
    return count


def _remove_empty_session_log_dirs(log_dir: Path) -> None:
    """删除日志清理后遗留的空 Session 目录。"""
    sessions_dir = log_dir / _SESSION_LOG_DIR_NAME
    if not sessions_dir.exists():
        return
    for session_dir in sessions_dir.iterdir():
        if not session_dir.is_dir():
            continue
        try:
            session_dir.rmdir()
        except OSError:
            # 目录仍有当前日志或其它文件时保留。
            continue
    try:
        sessions_dir.rmdir()
    except OSError:
        # 仍包含 Session 目录时保留根目录。
        return
