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

    @classmethod
    def _load(cls) -> dict:
        """加载元数据配置。"""
        if not cls.META_FILE.exists():
            return {}
        try:
            with open(cls.META_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            LOGGER.error(f"读取模型元数据失败: {e}")
            return {}

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
        return data.get(norm_path, os.path.basename(file_path))

    @classmethod
    def set_name(cls, file_path: str, name: str):
        """设置模型的显示名称。

        Args:
            file_path (str): 模型文件的绝对路径。
            name (str): 自定义显示名称。
        """
        data = cls._load()
        norm_path = os.path.normpath(file_path)
        data[norm_path] = name
        cls._save(data)
        
    @classmethod
    def remove_name(cls, file_path: str):
        """移除指定模型的名称映射。

        Args:
            file_path (str): 模型文件的绝对路径。
        """
        data = cls._load()
        norm_path = os.path.normpath(file_path)
        if norm_path in data:
            del data[norm_path]
            cls._save(data)
