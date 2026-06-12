"""导入文件列表管理器。

该模块负责导入文件列表的加载、保存、扫描合并、排序和列表移除操作，不依赖 UI 层。

Example:
    >>> manager = ImportFileListManager()
    >>> isinstance(manager.to_table_rows(), dict)
    True
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from infra.import_file_list_store import ImportFileListStore

FileTableRow = tuple[str, str, str]
FileScanResult = dict[str, list[FileTableRow]]
ImportSortKey = Literal["name", "size", "date"]


@dataclass(frozen=True)
class ImportFileEntry:
    """导入文件条目。

    保存排序、持久化和展示所需的完整文件元信息。

    Attributes:
        path: 文件完整路径。
        format_key: 文件格式键，取值为 ``excel``、``bin``、``mat``。
        display_name: 表格中展示的名称，后续重命名功能只需修改该字段。
        name: 磁盘文件原始名称。
        modified_timestamp: 文件修改时间戳。
        size_bytes: 文件大小，单位为字节。
    """

    path: Path
    format_key: str
    display_name: str
    name: str
    modified_timestamp: float
    size_bytes: int


class ImportFileListManager:
    """导入文件列表管理器。

    负责维护导入文件列表状态，并将用户对列表的移除和排序操作持久化保存。

    Attributes:
        format_extensions: 文件格式到扩展名集合的映射。
        files_by_type: 当前文件条目列表，按格式分组。
        ignored_paths: 用户移除过的文件路径集合，刷新扫描时不会重新加入。
        sort_key: 当前排序字段。
        sort_ascending: 当前是否升序排序。
        store: 导入文件列表状态存储。
    """

    format_extensions: dict[str, set[str]] = {
        "excel": {".xls", ".xlsx", ".xlsm"},
        "bin": {".bin"},
        "mat": {".mat"},
    }

    def __init__(self, store: ImportFileListStore | None = None) -> None:
        """初始化导入文件列表管理器。

        Args:
            store: 导入文件列表状态存储；为空时使用默认 JSON 存储。

        Returns:
            None: 无返回值。

        Raises:
            无显式抛出异常。
        """
        self.store = store or ImportFileListStore()
        self.files_by_type: dict[str, list[ImportFileEntry]] = self._empty_entries()
        self.ignored_paths: set[str] = set()
        self.sort_key: ImportSortKey = "name"
        self.sort_ascending: bool = True
        self.load()

    def load(self) -> FileScanResult:
        """从持久化文件加载导入文件列表状态。

        Args:
            无。

        Returns:
            加载后的表格行数据。

        Raises:
            无显式抛出异常；状态文件不存在或损坏时使用默认状态。

        Example:
            >>> manager = ImportFileListManager()
            >>> isinstance(manager.load(), dict)
            True
        """
        state = self.store.load()
        self.files_by_type = self._entries_from_state(state)
        self.ignored_paths = set(state["ignored_paths"])
        self.sort_key = state["sort"]["key"]
        self.sort_ascending = state["sort"]["ascending"]
        return self.sort(self.sort_key, self.sort_ascending, save_state=False)

    def scan(self, directories: list[str]) -> FileScanResult:
        """扫描导入目录直属文件并增量合并到当前列表。

        Args:
            directories: 待扫描目录路径列表；不存在或不可访问的路径会被跳过。

        Returns:
            合并新文件后的表格行数据。

        Raises:
            OSError: 当状态文件保存失败时抛出。

        Example:
            >>> manager = ImportFileListManager()
            >>> manager.scan([])
            {'excel': [], 'bin': [], 'mat': []}
        """
        for directory in directories:
            root = Path(directory).expanduser()
            if not root.is_dir():
                continue

            try:
                children = list(root.iterdir())
            except OSError:
                continue

            for file_path in children:
                # 仅处理直属普通文件，避免递归扫描大目录阻塞首页。
                if not file_path.is_file():
                    continue

                entry = self._build_entry(file_path)
                if entry is not None and not self._has_entry(entry.path):
                    self.files_by_type[entry.format_key].append(entry)

        return self.sort(self.sort_key, self.sort_ascending)

    def remove_at(self, format_key: str, row_index: int) -> FileScanResult:
        """从当前列表中移除指定格式的指定行并保存状态。

        该方法只移除列表项，不删除磁盘文件；被移除路径会进入忽略集合，后续刷新不会重新加入。

        Args:
            format_key: 文件格式键，取值为 ``excel``、``bin``、``mat``。
            row_index: 当前表格中的行索引，必须大于等于 0。

        Returns:
            移除后的表格行数据。

        Raises:
            OSError: 当状态文件保存失败时抛出。

        Example:
            >>> manager = ImportFileListManager()
            >>> manager.remove_at("excel", 0)
            {'excel': [], 'bin': [], 'mat': []}
        """
        rows = self.files_by_type.get(format_key)
        if rows is not None and 0 <= row_index < len(rows):
            entry = rows.pop(row_index)
            self.ignored_paths.add(self._normalize_path(entry.path))
            self.save()
        return self.to_table_rows()

    def sort(
        self,
        sort_key: ImportSortKey,
        ascending: bool = True,
        save_state: bool = True,
    ) -> FileScanResult:
        """按指定条件排序当前文件列表。

        Args:
            sort_key: 排序字段，支持 ``name``、``size``、``date``。
            ascending: True 表示升序，False 表示降序。
            save_state: True 表示排序后保存排序状态，False 表示只调整内存顺序。

        Returns:
            排序后的表格行数据。

        Raises:
            OSError: 当状态文件保存失败时抛出。

        Example:
            >>> manager = ImportFileListManager()
            >>> manager.sort("name")
            {'excel': [], 'bin': [], 'mat': []}
        """
        if sort_key not in {"name", "size", "date"}:
            sort_key = "name"
        self.sort_key = sort_key
        self.sort_ascending = ascending

        for rows in self.files_by_type.values():
            rows.sort(key=self._build_sort_value(sort_key), reverse=not ascending)

        if save_state:
            self.save()
        return self.to_table_rows()

    def save(self) -> None:
        """保存当前导入文件列表状态。

        Args:
            无。

        Returns:
            None: 无返回值。

        Raises:
            OSError: 当状态文件写入失败时抛出。
        """
        self.store.save(self._to_state())

    def to_table_rows(self) -> FileScanResult:
        """将当前内部文件条目转换为表格行数据。

        Args:
            无。

        Returns:
            按格式分组的表格行数据。

        Raises:
            无显式抛出异常。

        Example:
            >>> manager = ImportFileListManager()
            >>> manager.to_table_rows()
            {'excel': [], 'bin': [], 'mat': []}
        """
        return {
            format_key: [self._entry_to_table_row(entry) for entry in entries]
            for format_key, entries in self.files_by_type.items()
        }

    def get_entry_at(self, format_key: str, row_index: int) -> ImportFileEntry | None:
        """获取指定格式与表格行对应的文件条目。

        Args:
            format_key: 文件格式键，取值通常为 ``excel``、``bin`` 或 ``mat``。
            row_index: 当前表格中的行索引，必须大于或等于 0。

        Returns:
            匹配到的文件条目；格式键不存在或行号越界时返回 None。

        Raises:
            无显式抛出异常。

        Example:
            >>> manager = ImportFileListManager()
            >>> manager.get_entry_at("excel", -1) is None
            True
        """
        rows = self.files_by_type.get(format_key)
        if rows is None or not (0 <= row_index < len(rows)):
            return None
        return rows[row_index]

    def _entries_from_state(self, state: dict[str, Any]) -> dict[str, list[ImportFileEntry]]:
        """从 JSON 状态构建文件条目分组。"""
        entries_by_type = self._empty_entries()
        for format_key, rows in state["files"].items():
            if format_key not in entries_by_type:
                continue
            for row in rows:
                entry = self._entry_from_state_row(format_key, row)
                if entry is not None:
                    entries_by_type[format_key].append(entry)
        return entries_by_type

    def _entry_from_state_row(
        self,
        format_key: str,
        row: dict[str, Any],
    ) -> ImportFileEntry | None:
        """从单条 JSON 状态构建文件条目。"""
        path_text = row.get("path")
        if not isinstance(path_text, str) or not path_text:
            return None

        path = Path(path_text)
        display_name = row.get("display_name")
        original_name = row.get("original_name")
        modified_timestamp = row.get("modified_timestamp")
        size_bytes = row.get("size_bytes")

        return ImportFileEntry(
            path=path,
            format_key=format_key,
            display_name=display_name if isinstance(display_name, str) else path.name,
            name=original_name if isinstance(original_name, str) else path.name,
            modified_timestamp=(
                float(modified_timestamp)
                if isinstance(modified_timestamp, int | float)
                else 0.0
            ),
            size_bytes=int(size_bytes) if isinstance(size_bytes, int | float) else 0,
        )

    def _to_state(self) -> dict[str, Any]:
        """将当前文件列表转换为 JSON 状态。"""
        return {
            "files": {
                format_key: [self._entry_to_state_row(entry) for entry in entries]
                for format_key, entries in self.files_by_type.items()
            },
            "ignored_paths": sorted(self.ignored_paths),
            "sort": {"key": self.sort_key, "ascending": self.sort_ascending},
        }

    def _entry_to_state_row(self, entry: ImportFileEntry) -> dict[str, Any]:
        """将文件条目转换为 JSON 状态行。"""
        return {
            "path": str(entry.path),
            "display_name": entry.display_name,
            "original_name": entry.name,
            "size_bytes": entry.size_bytes,
            "modified_timestamp": entry.modified_timestamp,
        }

    def _empty_entries(self) -> dict[str, list[ImportFileEntry]]:
        """创建空的格式分组文件条目字典。"""
        return {key: [] for key in self.format_extensions}

    def _build_entry(self, file_path: Path) -> ImportFileEntry | None:
        """根据文件路径构建导入文件条目。"""
        format_key = self._resolve_format_key(file_path)
        if format_key is None:
            return None

        try:
            stat_result = file_path.stat()
        except OSError:
            return None

        return ImportFileEntry(
            path=file_path,
            format_key=format_key,
            display_name=file_path.name,
            name=file_path.name,
            modified_timestamp=stat_result.st_mtime,
            size_bytes=stat_result.st_size,
        )

    def _resolve_format_key(self, file_path: Path) -> str | None:
        """根据文件扩展名解析导入格式。"""
        suffix = file_path.suffix.lower()
        for format_key, extensions in self.format_extensions.items():
            if suffix in extensions:
                return format_key
        return None

    def _has_entry(self, file_path: Path) -> bool:
        """判断当前列表或忽略集合中是否已包含文件路径。"""
        normalized_path = self._normalize_path(file_path)
        if normalized_path in self.ignored_paths:
            return True
        return any(
            self._normalize_path(entry.path) == normalized_path
            for entries in self.files_by_type.values()
            for entry in entries
        )

    def _normalize_path(self, file_path: Path) -> str:
        """规范化文件路径用于去重。"""
        try:
            resolved_path = file_path.expanduser().resolve()
        except OSError:
            resolved_path = file_path.expanduser().absolute()
        return str(resolved_path).casefold()

    def _build_sort_value(self, sort_key: str) -> Callable[[ImportFileEntry], object]:
        """构建排序取值函数。"""
        if sort_key == "size":
            return lambda entry: (entry.size_bytes, entry.display_name.lower())
        if sort_key == "date":
            return lambda entry: (entry.modified_timestamp, entry.display_name.lower())
        return lambda entry: entry.display_name.lower()

    def _entry_to_table_row(self, entry: ImportFileEntry) -> FileTableRow:
        """将文件条目转换为表格展示行。"""
        modified_time = datetime.fromtimestamp(entry.modified_timestamp).strftime("%Y-%m-%d %H:%M")
        file_size = self._format_file_size(entry.size_bytes)
        return entry.display_name, modified_time, file_size

    def _format_file_size(self, size_bytes: int) -> str:
        """将字节数格式化为便于表格展示的文本。"""
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(max(size_bytes, 0))
        for unit in units:
            if size < 1024 or unit == units[-1]:
                if unit == "B":
                    return f"{int(size)} {unit}"
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
