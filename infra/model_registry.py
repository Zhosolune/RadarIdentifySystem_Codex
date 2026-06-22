# -*- coding: utf-8 -*-
"""模型元数据注册表，用于管理模型的别名，避免直接修改模型源文件。"""

import json
import os
import logging
from utils.paths import get_config_dir

LOGGER = logging.getLogger(__name__)

class ModelRegistry:
    """模型元数据注册表。

    提供模型自定义名称与备注的持久化存储与查询。
    """
    
    # 默认保存在 config 目录下，避免打包后写入 resources 失败
    META_FILE = get_config_dir() / "meta.json"

    @classmethod
    def _normalize_data(cls, raw_data: dict) -> dict:
        """标准化元数据结构。

        Args:
            raw_data (dict): 原始元数据对象。

        Returns:
            dict: 统一后的结构，包含 ``names`` 与 ``remarks`` 两个键。

        Raises:
            无。
        """
        names = raw_data.get("names", {})
        remarks = raw_data.get("remarks", {})
        return {
            "names": names if isinstance(names, dict) else {},
            "remarks": remarks if isinstance(remarks, dict) else {},
        }

    @classmethod
    def _load(cls) -> dict:
        """加载元数据配置。"""
        if not cls.META_FILE.exists():
            return {"names": {}, "remarks": {}}
        try:
            with open(cls.META_FILE, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
                return cls._normalize_data(raw_data)
        except Exception as e:
            LOGGER.error(f"读取模型元数据失败: {e}")
            return {"names": {}, "remarks": {}}

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
        if norm_path in data["remarks"]:
            # 清理备注映射
            del data["remarks"][norm_path]
        cls._save(data)

    @classmethod
    def get_remark(cls, file_path: str) -> str:
        """获取模型备注信息。

        Args:
            file_path (str): 模型文件的绝对路径。

        Returns:
            str: 配置中的备注信息，未配置时返回空字符串。

        Raises:
            无。
        """
        data = cls._load()
        norm_path = os.path.normpath(file_path)
        remark = data["remarks"].get(norm_path, "")
        return remark if isinstance(remark, str) else ""

    @classmethod
    def set_remark(cls, file_path: str, remark: str) -> None:
        """设置模型备注信息。

        Args:
            file_path (str): 模型文件的绝对路径。
            remark (str): 模型备注文本。

        Returns:
            None: 无返回值。

        Raises:
            无。
        """
        data = cls._load()
        norm_path = os.path.normpath(file_path)
        normalized_remark = remark.strip()
        if normalized_remark:
            # 写入模型备注
            data["remarks"][norm_path] = normalized_remark
        elif norm_path in data["remarks"]:
            # 删除空备注
            del data["remarks"][norm_path]
        cls._save(data)
