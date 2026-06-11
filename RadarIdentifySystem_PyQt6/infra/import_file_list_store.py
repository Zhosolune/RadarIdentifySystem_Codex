"""导入文件列表 JSON 存储。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from utils.paths import get_import_file_list_path


class ImportFileListStore:
    """导入文件列表状态存储。

    使用独立 JSON 文件保存导入文件列表、忽略路径和排序选项。

    Attributes:
        file_path: 状态文件路径。
    """

    def __init__(self, file_path: Path | None = None) -> None:
        """初始化导入文件列表存储。

        Args:
            file_path: 状态文件路径；为空时使用路径工具提供的默认位置。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        self.file_path = file_path or get_import_file_list_path()

    def load(self) -> dict[str, Any]:
        """读取导入文件列表状态。

        Args:
            无。

        Returns:
            JSON 状态字典；文件不存在、损坏或结构非法时返回默认状态。

        Raises:
            无显式抛出异常。

        Example:
            >>> state = ImportFileListStore().load()
            >>> "files" in state
            True
        """
        if not self.file_path.exists():
            return self.default_state()

        try:
            with self.file_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return self.default_state()

        if not isinstance(data, dict):
            return self.default_state()
        return self._normalize_state(data)

    def save(self, state: dict[str, Any]) -> None:
        """保存导入文件列表状态。

        Args:
            state: 需要保存的状态字典。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 当目录创建或文件写入失败时抛出。

        Example:
            >>> store = ImportFileListStore()
            >>> state = store.default_state()
            >>> isinstance(state, dict)
            True
        """
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_state = self._normalize_state(state)
        with self.file_path.open("w", encoding="utf-8") as file:
            json.dump(normalized_state, file, ensure_ascii=False, indent=4)

    def default_state(self) -> dict[str, Any]:
        """创建默认导入文件列表状态。

        Args:
            无。

        Returns:
            默认状态字典。

        Raises:
            无显式抛出异常。
        """
        return {
            "files": {"excel": [], "bin": [], "mat": []},
            "ignored_paths": [],
            "sort": {"key": "name", "ascending": True},
        }

    def _normalize_state(self, data: dict[str, Any]) -> dict[str, Any]:
        """规范化外部读取的状态结构。"""
        state = self.default_state()

        files = data.get("files")
        if isinstance(files, dict):
            for format_key in state["files"]:
                entries = files.get(format_key)
                if isinstance(entries, list):
                    state["files"][format_key] = [
                        entry for entry in entries if isinstance(entry, dict)
                    ]

        ignored_paths = data.get("ignored_paths")
        if isinstance(ignored_paths, list):
            state["ignored_paths"] = [
                path for path in ignored_paths if isinstance(path, str)
            ]

        sort_state = data.get("sort")
        if isinstance(sort_state, dict):
            key = sort_state.get("key")
            ascending = sort_state.get("ascending")
            if key in {"name", "size", "date"}:
                state["sort"]["key"] = key
            if isinstance(ascending, bool):
                state["sort"]["ascending"] = ascending

        return state
