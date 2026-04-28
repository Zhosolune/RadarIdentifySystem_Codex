# -*- coding: utf-8 -*-
"""模型元数据注册表，用于管理模型的别名，避免直接修改模型源文件。"""

import json
import os
import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)

class ModelRegistry:
    """模型元数据注册表。

    提供模型自定义名称的持久化存储与查询，避免重命名时修改实际模型文件。
    """
    
    # 默认保存在 resources/models 目录下
    META_FILE = Path(__file__).parent.parent / "resources" / "models" / "meta.json"
    SUPPORTED_TYPES = ("PA", "DTOA")

    @classmethod
    def _normalize_data(cls, raw_data: dict) -> dict:
        """标准化元数据结构。

        Args:
            raw_data (dict): 原始元数据对象，可能为旧版结构。

        Returns:
            dict: 统一后的结构，包含 ``names`` 与 ``enabled`` 两个键。

        Raises:
            无。
        """
        # 兼容旧版“路径 -> 名称”的平铺字典
        if "names" not in raw_data and "enabled" not in raw_data:
            return {
                "names": dict(raw_data),
                "enabled": {"PA": None, "DTOA": None},
            }

        names = raw_data.get("names", {})
        enabled = raw_data.get("enabled", {})
        return {
            "names": names if isinstance(names, dict) else {},
            "enabled": {
                "PA": enabled.get("PA"),
                "DTOA": enabled.get("DTOA"),
            },
        }

    @classmethod
    def _load(cls) -> dict:
        """加载元数据配置。"""
        if not cls.META_FILE.exists():
            return {"names": {}, "enabled": {"PA": None, "DTOA": None}}
        try:
            with open(cls.META_FILE, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
                return cls._normalize_data(raw_data)
        except Exception as e:
            LOGGER.error(f"读取模型元数据失败: {e}")
            return {"names": {}, "enabled": {"PA": None, "DTOA": None}}

    @classmethod
    def _save(cls, data: dict):
        """保存元数据配置。"""
        try:
            cls.META_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(cls.META_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            LOGGER.error(f"保存模型元数据失败: {e}")

    @classmethod
    def get_name(cls, file_path: str) -> str:
        """获取模型的显示名称。

        Args:
            file_path (str): 模型文件的绝对路径。

        Returns:
            str: 配置中的别名，若无则返回文件名。
        """
        data = cls._load()
        norm_path = os.path.normpath(file_path)
        return data["names"].get(norm_path, os.path.basename(file_path))

    @classmethod
    def set_name(cls, file_path: str, name: str):
        """设置模型的显示名称。

        Args:
            file_path (str): 模型文件的绝对路径。
            name (str): 自定义显示名称。
        """
        data = cls._load()
        norm_path = os.path.normpath(file_path)
        data["names"][norm_path] = name
        cls._save(data)
        
    @classmethod
    def remove_name(cls, file_path: str):
        """移除指定模型的名称映射。

        Args:
            file_path (str): 模型文件的绝对路径。
        """
        data = cls._load()
        norm_path = os.path.normpath(file_path)
        if norm_path in data["names"]:
            del data["names"][norm_path]
        # 删除模型时同步清理启用配置
        for model_type in cls.SUPPORTED_TYPES:
            if data["enabled"].get(model_type) == norm_path:
                data["enabled"][model_type] = None
        cls._save(data)

    @classmethod
    def get_enabled_model(cls, model_type: str) -> str | None:
        """获取指定类型当前启用的模型路径。

        Args:
            model_type (str): 模型类型，支持 ``PA`` 或 ``DTOA``。

        Returns:
            str | None: 启用模型路径，未配置时返回 None。

        Raises:
            ValueError: 传入模型类型不受支持时抛出。
        """
        if model_type not in cls.SUPPORTED_TYPES:
            raise ValueError(f"不支持的模型类型: {model_type}")
        data = cls._load()
        enabled_path = data["enabled"].get(model_type)
        return os.path.normpath(enabled_path) if enabled_path else None

    @classmethod
    def set_enabled_model(cls, model_type: str, file_path: str) -> None:
        """设置指定类型启用模型。

        Args:
            model_type (str): 模型类型，支持 ``PA`` 或 ``DTOA``。
            file_path (str): 待启用模型绝对路径。

        Returns:
            None: 无返回值。

        Raises:
            ValueError: 传入模型类型不受支持时抛出。
        """
        if model_type not in cls.SUPPORTED_TYPES:
            raise ValueError(f"不支持的模型类型: {model_type}")
        data = cls._load()
        data["enabled"][model_type] = os.path.normpath(file_path)
        cls._save(data)

    @classmethod
    def is_enabled(cls, model_type: str, file_path: str) -> bool:
        """判断模型是否为当前类型的启用模型。

        Args:
            model_type (str): 模型类型。
            file_path (str): 模型路径。

        Returns:
            bool: 匹配当前启用路径则返回 True，否则返回 False。

        Raises:
            ValueError: 传入模型类型不受支持时抛出。
        """
        enabled_path = cls.get_enabled_model(model_type)
        return enabled_path == os.path.normpath(file_path)

    @classmethod
    def ensure_enabled_model(cls, model_type: str, model_files: list[str]) -> str | None:
        """确保指定类型存在且仅存在一个可用启用模型。

        Args:
            model_type (str): 模型类型，支持 ``PA`` 或 ``DTOA``。
            model_files (list[str]): 当前目录中的模型路径列表。

        Returns:
            str | None: 最终生效的启用模型路径；无可用模型时返回 None。

        Raises:
            ValueError: 传入模型类型不受支持时抛出。
        """
        if model_type not in cls.SUPPORTED_TYPES:
            raise ValueError(f"不支持的模型类型: {model_type}")

        norm_files = [os.path.normpath(path) for path in model_files]
        if not norm_files:
            data = cls._load()
            data["enabled"][model_type] = None
            cls._save(data)
            return None

        current_enabled = cls.get_enabled_model(model_type)
        if current_enabled in norm_files:
            return current_enabled

        # 若目录仅有一个模型，则默认启用该模型；否则兜底启用第一个模型
        target_enabled = norm_files[0]
        cls.set_enabled_model(model_type, target_enabled)
        return target_enabled
