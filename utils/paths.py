"""集中解析只读程序资源与当前用户可写运行数据路径。

本模块只计算路径，不执行旧数据迁移等业务操作。安装版使用
``RadarIdentifySystem``，源码开发版使用 ``RadarIdentifySystem-Dev``，从而
避免两套配置和持久化数据互相污染。

Example:
    >>> paths = build_app_paths(packaged=False, data_root=Path("runtime-data"))
    >>> paths.app_name
    'RadarIdentifySystem-Dev'
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Final

_APP_NAME: Final[str] = "RadarIdentifySystem"
_DEV_APP_NAME: Final[str] = "RadarIdentifySystem-Dev"
_DATA_ROOT_ENV: Final[str] = "RADAR_IDENTIFY_DATA_ROOT"
_TEMP_ROOT_ENV: Final[str] = "RADAR_IDENTIFY_TEMP_ROOT"
_RUN_ID: Final[str] = f"{datetime.now():%Y%m%d_%H%M%S}_{os.getpid()}"


def _default_user_data_root(app_name: str) -> Path:
    """按当前操作系统返回用户本地应用数据目录。"""
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        base_dir = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base_dir / app_name
    xdg_data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    base_dir = Path(xdg_data_home) if xdg_data_home else Path.home() / ".local" / "share"
    return base_dir / app_name


@dataclass(frozen=True, slots=True)
class AppPaths:
    """保存应用全部稳定路径。

    Attributes:
        app_name: 当前运行配置使用的应用名称。
        packaged: 是否运行在冻结后的安装版本中。
        install_root: 可执行程序安装根目录。
        resource_root: Python 模块和 ``resources`` 所在的只读根目录。
        user_data_root: 当前用户可写数据根目录。
        system_temp_root: 操作系统临时目录下的应用根目录。
    """

    app_name: str
    packaged: bool
    install_root: Path
    resource_root: Path
    user_data_root: Path
    system_temp_root: Path

    @property
    def config_dir(self) -> Path:
        """返回配置目录。"""
        return self.user_data_root / "config"

    @property
    def config_file(self) -> Path:
        """返回全局配置文件。"""
        return self.config_dir / "config.json"

    @property
    def import_file_list_file(self) -> Path:
        """返回导入文件列表状态文件。"""
        return self.config_dir / "import_file_list.json"

    @property
    def model_metadata_file(self) -> Path:
        """返回用户模型元数据文件。"""
        return self.config_dir / "model_meta.json"

    @property
    def log_dir(self) -> Path:
        """返回日志根目录。"""
        return self.user_data_root / "logs"

    @property
    def session_dir(self) -> Path:
        """返回交互式 Session 持久化目录。"""
        return self.user_data_root / "data" / "sessions" / "interactive"

    @property
    def full_speed_session_dir(self) -> Path:
        """返回全速 Session 持久化目录。"""
        return self.user_data_root / "data" / "sessions" / "full_speed"

    @property
    def data_pool_dir(self) -> Path:
        """返回数据池持久化目录。"""
        return self.user_data_root / "data" / "data_pool"

    @property
    def user_model_dir(self) -> Path:
        """返回用户导入模型根目录。"""
        return self.user_data_root / "models"

    @property
    def cache_dir(self) -> Path:
        """返回可重建缓存目录。"""
        return self.user_data_root / "cache"

    @property
    def runtime_temp_dir(self) -> Path:
        """返回当前进程独立的临时目录。"""
        return self.system_temp_root / _RUN_ID

    @property
    def resources_dir(self) -> Path:
        """返回只读资源目录。"""
        return self.resource_root / "resources"

    def builtin_model_dir(self, model_type: str) -> Path:
        """返回指定类型的内置模型目录。

        Args:
            model_type [str]: 模型类型，当前使用 ``PA`` 或 ``DTOA``。

        Returns:
            Path: 安装资源中的只读模型目录。

        Raises:
            ValueError: 模型类型为空或包含路径分隔符时抛出。

        Example:
            >>> paths = build_app_paths(packaged=False, data_root=Path("data"))
            >>> paths.builtin_model_dir("pa").name
            'PA'
        """
        normalized_type = model_type.strip().upper()
        if not normalized_type or Path(normalized_type).name != normalized_type:
            raise ValueError("模型类型必须是单一目录名")
        return self.resources_dir / "models" / normalized_type


def is_packaged_runtime() -> bool:
    """判断当前是否为 PyInstaller 等冻结运行环境。

    Returns:
        bool: 冻结运行时返回 True，否则返回 False。

    Raises:
        无。

    Example:
        >>> isinstance(is_packaged_runtime(), bool)
        True
    """
    return bool(getattr(sys, "frozen", False))


def build_app_paths(
    *,
    packaged: bool | None = None,
    data_root: Path | None = None,
    resource_root: Path | None = None,
    install_root: Path | None = None,
    temp_root: Path | None = None,
) -> AppPaths:
    """构造一组不产生磁盘写入的应用路径。

    Args:
        packaged [bool | None]: 是否按冻结环境构造；为空时自动检测。
        data_root [Path | None]: 测试或嵌入场景使用的用户数据根目录。
        resource_root [Path | None]: 只读资源根目录覆盖值。
        install_root [Path | None]: 安装根目录覆盖值。
        temp_root [Path | None]: 系统临时目录下的应用根目录覆盖值。

    Returns:
        AppPaths: 完整的路径值对象，不会自动创建任何目录。

    Raises:
        OSError: 解析路径失败时由 ``Path.resolve`` 抛出。

    Example:
        >>> paths = build_app_paths(packaged=True, data_root=Path("user-data"))
        >>> paths.session_dir.parts[-2:]
        ('sessions', 'interactive')
    """
    packaged_runtime = is_packaged_runtime() if packaged is None else packaged
    app_name = _APP_NAME if packaged_runtime else _DEV_APP_NAME
    source_root = Path(__file__).resolve().parents[1]
    bundle_root_value = getattr(sys, "_MEIPASS", source_root)
    default_resource_root = (
        Path(bundle_root_value) if packaged_runtime else source_root
    )
    resolved_resource_root = (resource_root or default_resource_root).resolve()
    default_install_root = (
        Path(sys.executable).resolve().parent
        if packaged_runtime
        else source_root
    )
    resolved_install_root = (install_root or default_install_root).resolve()

    environment_data_root = os.environ.get(_DATA_ROOT_ENV, "").strip()
    selected_data_root = data_root
    if selected_data_root is None and environment_data_root:
        selected_data_root = Path(environment_data_root)
    if selected_data_root is None:
        selected_data_root = _default_user_data_root(app_name)

    environment_temp_root = os.environ.get(_TEMP_ROOT_ENV, "").strip()
    selected_temp_root = temp_root
    if selected_temp_root is None and environment_temp_root:
        selected_temp_root = Path(environment_temp_root)
    if selected_temp_root is None:
        selected_temp_root = Path(tempfile.gettempdir()) / app_name

    return AppPaths(
        app_name=app_name,
        packaged=packaged_runtime,
        install_root=resolved_install_root,
        resource_root=resolved_resource_root,
        user_data_root=selected_data_root.expanduser().resolve(),
        system_temp_root=selected_temp_root.expanduser().resolve(),
    )


def get_app_paths() -> AppPaths:
    """返回当前进程使用的应用路径。

    Returns:
        AppPaths: 按冻结状态和环境覆盖值构造的路径对象。

    Raises:
        OSError: 路径解析失败时抛出。

    Example:
        >>> isinstance(get_app_paths(), AppPaths)
        True
    """
    return build_app_paths()


def _ensure_directory(path: Path) -> Path:
    """创建并返回指定目录。"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_project_root() -> Path:
    """返回源码或冻结资源根目录。

    Returns:
        Path: 包含项目 Python 包和 ``resources`` 的目录。

    Raises:
        RuntimeError: 推导出的资源根目录不存在时抛出。

    Example:
        >>> get_project_root().exists()
        True
    """
    root = get_app_paths().resource_root
    if not root.exists():
        raise RuntimeError("应用资源根目录不存在")
    return root


def get_install_root() -> Path:
    """返回只读程序安装目录。

    Returns:
        Path: 安装版可执行文件目录，开发版返回项目根目录。

    Raises:
        无显式抛出异常。

    Example:
        >>> get_install_root().is_absolute()
        True
    """
    return get_app_paths().install_root


def get_resources_dir() -> Path:
    """返回只读资源目录。

    Returns:
        Path: ``resources`` 目录路径。

    Raises:
        无显式抛出异常。

    Example:
        >>> get_resources_dir().name
        'resources'
    """
    return get_app_paths().resources_dir


def get_config_dir() -> Path:
    """创建并返回用户配置目录。

    Returns:
        Path: LocalAppData 下的配置目录。

    Raises:
        OSError: 配置目录创建失败时抛出。

    Example:
        >>> get_config_dir().name
        'config'
    """
    return _ensure_directory(get_app_paths().config_dir)


def get_config_file_path() -> Path:
    """返回全局配置文件路径。

    Returns:
        Path: ``config/config.json`` 的绝对路径。

    Raises:
        OSError: 配置目录创建失败时抛出。

    Example:
        >>> get_config_file_path().name
        'config.json'
    """
    return get_config_dir() / "config.json"


def get_model_metadata_file_path() -> Path:
    """返回用户模型元数据文件路径。

    Returns:
        Path: ``config/model_meta.json`` 的绝对路径。

    Raises:
        OSError: 配置目录创建失败时抛出。

    Example:
        >>> get_model_metadata_file_path().name
        'model_meta.json'
    """
    return get_config_dir() / "model_meta.json"


def get_session_config_dir() -> Path:
    """创建并返回交互式 Session 持久化目录。

    Returns:
        Path: ``data/sessions/interactive`` 目录。

    Raises:
        OSError: 目录创建失败时抛出。

    Example:
        >>> get_session_config_dir().name
        'interactive'
    """
    return _ensure_directory(get_app_paths().session_dir)


def get_full_speed_session_dir() -> Path:
    """创建并返回全速 Session 持久化目录。

    Returns:
        Path: ``data/sessions/full_speed`` 目录。

    Raises:
        OSError: 目录创建失败时抛出。

    Example:
        >>> get_full_speed_session_dir().name
        'full_speed'
    """
    return _ensure_directory(get_app_paths().full_speed_session_dir)


def get_data_pool_dir(*, create: bool = True) -> Path:
    """返回数据池持久化目录。

    Args:
        create [bool]: 是否立即创建目录，默认 True。

    Returns:
        Path: ``data/data_pool`` 目录。

    Raises:
        OSError: ``create`` 为 True 且目录创建失败时抛出。

    Example:
        >>> get_data_pool_dir().name
        'data_pool'
    """
    path = get_app_paths().data_pool_dir
    return _ensure_directory(path) if create else path


def get_import_file_list_path() -> Path:
    """返回导入文件列表状态文件路径。

    Returns:
        Path: ``config/import_file_list.json`` 的绝对路径。

    Raises:
        OSError: 配置目录创建失败时抛出。

    Example:
        >>> get_import_file_list_path().name
        'import_file_list.json'
    """
    return get_config_dir() / "import_file_list.json"


def get_log_dir() -> Path:
    """创建并返回日志根目录。

    Returns:
        Path: LocalAppData 下的日志目录。

    Raises:
        OSError: 日志目录创建失败时抛出。

    Example:
        >>> get_log_dir().name
        'logs'
    """
    return _ensure_directory(get_app_paths().log_dir)


def get_user_model_root_dir() -> Path:
    """返回用户导入模型根目录。

    Returns:
        Path: LocalAppData 下的 ``models`` 目录。

    Raises:
        无显式抛出异常。

    Example:
        >>> get_user_model_root_dir().name
        'models'
    """
    return get_app_paths().user_model_dir


def get_builtin_model_dir(model_type: str) -> Path:
    """返回指定类型的只读内置模型目录。

    Args:
        model_type [str]: 模型类型，例如 ``PA`` 或 ``DTOA``。

    Returns:
        Path: 安装资源中的模型目录。

    Raises:
        ValueError: 模型类型不是安全目录名时抛出。

    Example:
        >>> get_builtin_model_dir("DTOA").name
        'DTOA'
    """
    return get_app_paths().builtin_model_dir(model_type)


def get_cache_dir() -> Path:
    """创建并返回可重建缓存目录。

    Returns:
        Path: LocalAppData 下的缓存目录。

    Raises:
        OSError: 目录创建失败时抛出。

    Example:
        >>> get_cache_dir().name
        'cache'
    """
    return _ensure_directory(get_app_paths().cache_dir)


def get_runtime_temp_dir() -> Path:
    """创建并返回当前进程独立临时目录。

    Returns:
        Path: 系统临时根目录下的当前进程目录。

    Raises:
        OSError: 临时目录创建失败时抛出。

    Example:
        >>> get_runtime_temp_dir().parent.name in {_APP_NAME, _DEV_APP_NAME}
        True
    """
    return _ensure_directory(get_app_paths().runtime_temp_dir)


def cleanup_runtime_temp_dir() -> None:
    """删除当前进程创建的临时目录。

    Returns:
        None: 目录不存在时不执行操作。

    Raises:
        OSError: 临时目录存在但无法删除时抛出。

    Example:
        >>> cleanup_runtime_temp_dir()
    """
    runtime_dir = get_app_paths().runtime_temp_dir
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
