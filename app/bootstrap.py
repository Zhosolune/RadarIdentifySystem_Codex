"""应用启动前存储准备与退出阶段临时目录清理。"""

from __future__ import annotations

from infra.legacy_data_migrator import LegacyMigrationResult, migrate_legacy_user_data
from utils.paths import (
    cleanup_runtime_temp_dir,
    get_cache_dir,
    get_config_dir,
    get_log_dir,
    get_runtime_temp_dir,
    get_user_model_root_dir,
)


def prepare_application_storage() -> LegacyMigrationResult:
    """在配置和日志模块导入前准备用户存储布局。

    Returns:
        LegacyMigrationResult: 旧目录迁移统计。

    Raises:
        OSError: 迁移或目录创建失败时抛出。
        ValueError: 旧版 JSON 数据损坏时抛出。

    Example:
        >>> result = prepare_application_storage()
        >>> isinstance(result, LegacyMigrationResult)
        True
    """
    migration_result = migrate_legacy_user_data()
    # 仅创建应用启动必需目录；Session 和数据池仍由各自 Store 延迟创建。
    get_config_dir()
    get_log_dir()
    get_cache_dir()
    get_runtime_temp_dir()
    user_model_root = get_user_model_root_dir()
    for model_type in ("PA", "DTOA"):
        (user_model_root / model_type).mkdir(parents=True, exist_ok=True)
    return migration_result


def cleanup_application_runtime() -> None:
    """清理当前进程拥有的临时目录。

    Returns:
        None: 无返回值。

    Raises:
        OSError: 当前进程临时目录无法删除时抛出。

    Example:
        >>> cleanup_application_runtime()
    """
    cleanup_runtime_temp_dir()
