"""模型配置初始化与查询工具。"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from qfluentwidgets import qconfig

from app.app_config import appConfig
from infra.model_registry import ModelRegistry

LOGGER = logging.getLogger(__name__)
SYSTEM_DEFAULT_NAME = "系统默认"
SUPPORTED_MODEL_TYPES = ("PA", "DTOA")
VALID_MODEL_SUFFIXES = (".onnx", ".pkl", ".pt", ".pth")

_cached_inference_service: Optional["OnnxInferenceService"] = None
_cached_pa_path: str | None = None
_cached_dtoa_path: str | None = None


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


def _get_enabled_path_config_item(model_type: str):
    """获取启用模型路径配置项。"""
    normalized_type = _normalize_model_type(model_type)
    if normalized_type == "PA":
        return appConfig.modelPaEnabledPath
    return appConfig.modelDtoaEnabledPath


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


def get_enabled_model_path(model_type: str) -> str | None:
    """读取当前启用模型路径。

    Args:
        model_type (str): 模型类型。

    Returns:
        str | None: 当前启用模型路径，无值时返回 None。

    Raises:
        ValueError: 模型类型不受支持时抛出异常。
    """
    config_item = _get_enabled_path_config_item(model_type)
    return _normalize_path(qconfig.get(config_item))


def set_enabled_model_path(model_type: str, file_path: str | None) -> None:
    """写入当前启用模型路径。

    Args:
        model_type (str): 模型类型。
        file_path (str | None): 启用模型路径，无值时清空配置。

    Returns:
        None: 无返回值。

    Raises:
        ValueError: 模型类型不受支持时抛出异常。
    """
    normalized_path = _normalize_path(file_path)
    enabled_item = _get_enabled_path_config_item(model_type)
    # 写入启用模型路径
    qconfig.set(enabled_item, normalized_path or "")


def resolve_enabled_model(
    model_type: str,
    model_files: list[str] | None = None,
) -> str | None:
    """解析并修正当前生效的启用模型。

    Args:
        model_type (str): 模型类型。
        model_files (list[str] | None): 可用模型列表，未传入时自动收集。

    Returns:
        str | None: 最终生效的启用模型路径，无可用模型时返回 None。

    Raises:
        ValueError: 模型类型不受支持时抛出异常。
    """
    normalized_files = [
        os.path.normpath(path)
        for path in (model_files if model_files is not None else collect_available_model_files(model_type))
    ]
    if not normalized_files:
        # 无模型时清空启用状态
        set_enabled_model_path(model_type, None)
        return None

    current_enabled = get_enabled_model_path(model_type)
    if current_enabled in normalized_files:
        # 保留有效的当前启用模型
        set_enabled_model_path(model_type, current_enabled)
        return current_enabled

    for file_path in normalized_files:
        if is_builtin_model(file_path, model_type):
            # 优先启用系统默认模型
            set_enabled_model_path(model_type, file_path)
            return file_path

    # 无系统默认模型时兜底启用首个可用模型
    set_enabled_model_path(model_type, normalized_files[0])
    return normalized_files[0]


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
    global _cached_inference_service, _cached_pa_path, _cached_dtoa_path
    if (
        _cached_inference_service is not None
        and _cached_pa_path == pa_path
        and _cached_dtoa_path == dtoa_path
    ):
        return _cached_inference_service

    from infra.onnx_service import OnnxInferenceService

    LOGGER.info("创建推理服务实例: PA=%s, DTOA=%s", pa_path, dtoa_path)
    _cached_inference_service = OnnxInferenceService(
        dtoa_model_path=dtoa_path,
        pa_model_path=pa_path,
        temp_dir=temp_dir,
    )
    _cached_pa_path = pa_path
    _cached_dtoa_path = dtoa_path
    return _cached_inference_service


def initialize_model_runtime(write_log: bool = True) -> dict[str, str | None]:
    """初始化全部模型类型的启用配置并预热推理服务。

    在应用启动阶段调用，完成模型配置解析与 ONNX 模型预加载，
    避免首次识别时主线程阻塞导致加载动画延迟。

    Args:
        write_log (bool): 是否输出初始化日志。

    Returns:
        dict[str, str | None]: 各模型类型最终生效的启用路径映射。

    Raises:
        ValueError: 模型类型不受支持时抛出异常。
    """
    from infra.onnx_service import OnnxInferenceService
    from app.app_config import qconfig

    global _cached_inference_service, _cached_pa_path, _cached_dtoa_path

    enabled_mapping: dict[str, str | None] = {}
    for model_type in SUPPORTED_MODEL_TYPES:
        model_files = collect_available_model_files(model_type)
        enabled_path = resolve_enabled_model(model_type, model_files=model_files)
        enabled_mapping[model_type] = enabled_path
        if not write_log:
            continue
        if enabled_path:
            LOGGER.info(
                "模型初始化成功: type=%s, name=%s, enabled=%s",
                model_type,
                get_display_name(enabled_path, model_type),
                enabled_path,
            )
        else:
            LOGGER.info(
                "模型初始化失败: type=%s, name=%s, enabled=%s",
                model_type,
                "未启用",
                "",
            )

    # 预加载推理服务，避免首次识别时主线程阻塞
    pa_path = enabled_mapping.get("PA")
    dtoa_path = enabled_mapping.get("DTOA")
    temp_dir = str(qconfig.get(appConfig.logDir))
    if pa_path and dtoa_path:
        LOGGER.info("开始预热推理服务...")
        _cached_inference_service = OnnxInferenceService(
            dtoa_model_path=dtoa_path,
            pa_model_path=pa_path,
            temp_dir=temp_dir,
        )
        _cached_pa_path = pa_path
        _cached_dtoa_path = dtoa_path
        LOGGER.info("推理服务预热完成")
    else:
        LOGGER.warning("预热跳过：启用模型路径为空")

    return enabled_mapping
