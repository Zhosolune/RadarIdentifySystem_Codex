"""模型配置初始化与查询工具。"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from threading import RLock

from qfluentwidgets import qconfig

from app.app_config import appConfig
from infra.model_registry import ModelRegistry

LOGGER = logging.getLogger(__name__)
SYSTEM_DEFAULT_NAME = "系统默认"
SUPPORTED_MODEL_TYPES = ("PA", "DTOA")
VALID_MODEL_SUFFIXES = (".onnx", ".pkl", ".pt", ".pth")

_inference_service_cache: dict[tuple[str, str, str], "OnnxInferenceService"] = {}
_inference_service_cache_lock = RLock()


def _normalize_model_type(model_type: str) -> str:
    """标准化模型类型。

    Args:
        model_type (str): 原始模型类型。

    Returns:
        str: 标准化后的模型类型。

    Raises:
        ValueError: 模型类型不受支持时抛出异常。
    """
    normalized_type = model_type.upper()
    if normalized_type not in SUPPORTED_MODEL_TYPES:
        raise ValueError(f"不支持的模型类型: {model_type}")
    return normalized_type


def _normalize_path(file_path: str | None) -> str | None:
    """标准化路径字符串。

    Args:
        file_path (str | None): 原始路径。

    Returns:
        str | None: 标准化后的路径，无值时返回 None。

    Raises:
        无。
    """
    if not file_path:
        return None
    return os.path.normpath(file_path)


def _get_enabled_paths_config_item(model_type: str):
    """获取启用模型路径列表配置项。"""
    normalized_type = _normalize_model_type(model_type)
    if normalized_type == "PA":
        return appConfig.modelPaEnabledPaths
    return appConfig.modelDtoaEnabledPaths


def _get_legacy_enabled_path_config_item(model_type: str):
    """获取旧版单模型路径配置项。"""
    normalized_type = _normalize_model_type(model_type)
    if normalized_type == "PA":
        return appConfig.modelPaEnabledPath
    return appConfig.modelDtoaEnabledPath


def _normalize_paths(value: object) -> list[str]:
    """将外部配置值标准化为去重路径列表。"""
    raw_paths = [value] if isinstance(value, str) else value
    if not isinstance(raw_paths, (list, tuple)):
        return []

    normalized_paths: list[str] = []
    for raw_path in raw_paths:
        normalized_path = _normalize_path(
            raw_path if isinstance(raw_path, str) else None
        )
        if normalized_path and normalized_path not in normalized_paths:
            normalized_paths.append(normalized_path)
    return normalized_paths


def get_user_model_root_dir() -> Path:
    """获取用户模型根目录。

    Args:
        无。

    Returns:
        Path: 用户模型根目录。

    Raises:
        无。
    """
    configured_root = qconfig.get(appConfig.userModelRootDir)
    default_root = Path.home() / ".RadarIdentifySystem" / "models"
    normalized_root = str(configured_root).strip() if configured_root else ""
    if not normalized_root:
        return default_root
    return Path(normalized_root)


def get_builtin_model_dir(model_type: str) -> Path:
    """获取系统内置模型目录。

    Args:
        model_type (str): 模型类型。

    Returns:
        Path: 系统内置模型目录。

    Raises:
        ValueError: 模型类型不受支持时抛出异常。
    """
    normalized_type = _normalize_model_type(model_type)
    # 返回资源目录中的内置模型路径
    return Path(__file__).resolve().parent.parent / "resources" / "models" / normalized_type


def get_user_model_dir(model_type: str) -> Path:
    """获取用户模型目录。

    Args:
        model_type (str): 模型类型。

    Returns:
        Path: 用户模型目录。

    Raises:
        ValueError: 模型类型不受支持时抛出异常。
    """
    normalized_type = _normalize_model_type(model_type)
    # 基于根目录推导模型类型子目录
    return get_user_model_root_dir() / normalized_type


def ensure_user_model_dir(model_type: str) -> Path:
    """确保用户模型目录存在。

    Args:
        model_type (str): 模型类型。

    Returns:
        Path: 用户模型目录。

    Raises:
        OSError: 创建目录失败时抛出异常。
    """
    user_dir = get_user_model_dir(model_type)
    # 创建用户模型目录
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def is_builtin_model(file_path: str, model_type: str) -> bool:
    """判断模型是否为系统内置模型。

    Args:
        file_path (str): 模型文件路径。
        model_type (str): 模型类型。

    Returns:
        bool: 属于系统内置目录时返回 True。

    Raises:
        ValueError: 模型类型不受支持时抛出异常。
    """
    builtin_dir = get_builtin_model_dir(model_type)
    return Path(file_path).parent.resolve() == builtin_dir.resolve()


def collect_available_model_files(model_type: str) -> list[str]:
    """收集可用模型文件列表。

    Args:
        model_type (str): 模型类型。

    Returns:
        list[str]: 去重并排序后的模型路径列表。

    Raises:
        ValueError: 模型类型不受支持时抛出异常。
    """
    ensure_user_model_dir(model_type)
    model_files: list[str] = []
    for model_dir in (get_builtin_model_dir(model_type), get_user_model_dir(model_type)):
        if not model_dir.exists():
            continue
        # 扫描可识别的模型文件
        for file_name in os.listdir(model_dir):
            if file_name.endswith(VALID_MODEL_SUFFIXES):
                model_files.append(str(model_dir / file_name))
    return sorted({os.path.normpath(path) for path in model_files})


def get_display_name(file_path: str, model_type: str) -> str:
    """获取模型展示名称。

    Args:
        file_path (str): 模型文件路径。
        model_type (str): 模型类型。

    Returns:
        str: 展示名称。

    Raises:
        ValueError: 模型类型不受支持时抛出异常。
    """
    if is_builtin_model(file_path, model_type):
        # 系统内置模型统一显示固定名称
        return SYSTEM_DEFAULT_NAME
    return ModelRegistry.get_name(file_path)


def get_enabled_model_paths(model_type: str) -> list[str]:
    """读取当前类型的启用模型路径列表。

    Args:
        model_type (str): 模型类型。

    Returns:
        list[str]: 去重后的启用模型路径列表，无值时返回空列表。

    Raises:
        ValueError: 模型类型不受支持时抛出异常。
    """
    paths_item = _get_enabled_paths_config_item(model_type)
    enabled_paths = _normalize_paths(qconfig.get(paths_item))
    if enabled_paths:
        return enabled_paths

    # 首次升级时把旧版单选路径迁移为只含一个元素的启用列表。
    legacy_item = _get_legacy_enabled_path_config_item(model_type)
    legacy_path = _normalize_path(qconfig.get(legacy_item))
    if legacy_path:
        qconfig.set(paths_item, [legacy_path])
        return [legacy_path]
    return []


def set_enabled_model_paths(model_type: str, file_paths: list[str]) -> None:
    """写入当前类型的启用模型路径列表。

    Args:
        model_type (str): 模型类型。
        file_paths (list[str]): 目标启用模型路径列表。

    Returns:
        None: 无返回值。

    Raises:
        ValueError: 模型类型不受支持时抛出异常。
    """
    normalized_paths = _normalize_paths(file_paths)
    paths_item = _get_enabled_paths_config_item(model_type)
    legacy_item = _get_legacy_enabled_path_config_item(model_type)
    # 同步保留旧字段的首项值，保证旧版本配置仍可降级读取。
    qconfig.set(paths_item, normalized_paths)
    qconfig.set(legacy_item, normalized_paths[0] if normalized_paths else "")


def set_model_enabled(model_type: str, file_path: str, enabled: bool) -> list[str]:
    """切换单个模型在启用列表中的状态。

    Args:
        model_type (str): 模型类型。
        file_path (str): 待切换的模型文件路径。
        enabled (bool): 为 True 时加入列表，否则移出列表。

    Returns:
        list[str]: 更新后的启用模型路径列表。

    Raises:
        ValueError: 模型类型不受支持或路径为空时抛出异常。
    """
    normalized_path = _normalize_path(file_path)
    if normalized_path is None:
        raise ValueError("模型路径不能为空")

    enabled_paths = get_enabled_model_paths(model_type)
    if enabled and normalized_path not in enabled_paths:
        enabled_paths.append(normalized_path)
    elif not enabled:
        enabled_paths = [path for path in enabled_paths if path != normalized_path]
    set_enabled_model_paths(model_type, enabled_paths)
    return enabled_paths


def resolve_enabled_models(
    model_type: str,
    model_files: list[str] | None = None,
) -> list[str]:
    """解析并修正当前类型的启用模型列表。

    Args:
        model_type (str): 模型类型。
        model_files (list[str] | None): 可用模型列表，未传入时自动收集。

    Returns:
        list[str]: 最终生效的启用模型路径列表，无可用模型时返回空列表。

    Raises:
        ValueError: 模型类型不受支持时抛出异常。
    """
    normalized_files = [
        os.path.normpath(path)
        for path in (model_files if model_files is not None else collect_available_model_files(model_type))
    ]
    if not normalized_files:
        # 无模型时清空启用状态
        set_enabled_model_paths(model_type, [])
        return []

    current_enabled = get_enabled_model_paths(model_type)
    normalized_file_set = set(normalized_files)
    valid_enabled = [path for path in current_enabled if path in normalized_file_set]
    if valid_enabled:
        # 丢弃已移除文件，同时保留用户启用顺序。
        set_enabled_model_paths(model_type, valid_enabled)
        return valid_enabled

    for file_path in normalized_files:
        if is_builtin_model(file_path, model_type):
            # 优先启用系统默认模型
            set_enabled_model_paths(model_type, [file_path])
            return [file_path]

    # 无系统默认模型时兜底启用首个可用模型
    set_enabled_model_paths(model_type, [normalized_files[0]])
    return [normalized_files[0]]


def get_cached_inference_service(
    pa_path: str,
    dtoa_path: str,
    temp_dir: str,
) -> "OnnxInferenceService":
    """获取或创建缓存的推理服务实例。

    若缓存的实例与请求的模型路径一致则直接返回，否则重建。
    此函数由 runtime 层在识别启动时调用。

    Args:
        pa_path (str): PA 模型路径。
        dtoa_path (str): DTOA 模型路径。
        temp_dir (str): 临时目录。

    Returns:
        OnnxInferenceService: 推理服务实例。

    Raises:
        无。
    """
    cache_key = (
        os.path.normcase(os.path.normpath(pa_path)),
        os.path.normcase(os.path.normpath(dtoa_path)),
        os.path.normcase(os.path.normpath(temp_dir)),
    )
    with _inference_service_cache_lock:
        cached_service = _inference_service_cache.get(cache_key)
        if cached_service is not None:
            return cached_service

        from infra.onnx_service import OnnxInferenceService

        LOGGER.debug("创建推理服务实例: PA=%s, DTOA=%s", pa_path, dtoa_path)
        service = OnnxInferenceService(
            dtoa_model_path=dtoa_path,
            pa_model_path=pa_path,
            temp_dir=temp_dir,
            reuse_model_sessions=True,
        )
        _inference_service_cache[cache_key] = service
        return service


def clear_cached_inference_services() -> None:
    """清空交互式推理服务组合缓存。

    Returns:
        None: 无返回值。

    Raises:
        无。
    """
    with _inference_service_cache_lock:
        _inference_service_cache.clear()
    from infra.onnx_service import clear_shared_model_session_cache

    clear_shared_model_session_cache()


def initialize_model_runtime(write_log: bool = True) -> dict[str, list[str]]:
    """初始化全部模型类型的启用配置并预热推理服务。

    在应用启动阶段调用，完成模型配置解析与 ONNX 模型预加载，
    避免首次识别时主线程阻塞导致加载动画延迟。

    Args:
        write_log (bool): 是否输出初始化日志。

    Returns:
        dict[str, list[str]]: 各模型类型最终生效的启用路径列表映射。

    Raises:
        ValueError: 模型类型不受支持时抛出异常。
    """
    from app.app_config import qconfig

    enabled_mapping: dict[str, list[str]] = {}
    for model_type in SUPPORTED_MODEL_TYPES:
        model_files = collect_available_model_files(model_type)
        enabled_paths = resolve_enabled_models(model_type, model_files=model_files)
        enabled_mapping[model_type] = enabled_paths
        if not write_log:
            continue
        if enabled_paths:
            LOGGER.info(
                "模型初始化成功: type=%s, enabled_count=%d, enabled=%s",
                model_type,
                len(enabled_paths),
                ", ".join(
                    get_display_name(path, model_type) for path in enabled_paths
                ),
            )
        else:
            LOGGER.warning(
                "模型初始化失败: type=%s, enabled_count=0",
                model_type,
            )

    # 预热全部可选组合；底层 ONNX Session 按单模型共享，避免组合数导致模型重复驻留。
    pa_paths = enabled_mapping.get("PA", [])
    dtoa_paths = enabled_mapping.get("DTOA", [])
    temp_dir = str(qconfig.get(appConfig.logDir))
    if pa_paths and dtoa_paths:
        combination_count = len(pa_paths) * len(dtoa_paths)
        LOGGER.info("开始预热推理服务: combinations=%d", combination_count)
        for pa_path in pa_paths:
            for dtoa_path in dtoa_paths:
                get_cached_inference_service(pa_path, dtoa_path, temp_dir)
        LOGGER.info("推理服务预热完成: combinations=%d", combination_count)
    else:
        LOGGER.warning("预热跳过：PA 或 DTOA 启用模型列表为空")

    return enabled_mapping
