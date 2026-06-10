"""导入目录文件扫描适配器。

该模块只处理文件系统扫描与文件元信息格式化，不依赖 UI 层。

Example:
    >>> result = scan_import_files([])
    >>> sorted(result)
    ['bin', 'excel', 'mat']
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

FileTableRow = tuple[str, str, str]
FileScanResult = dict[str, list[FileTableRow]]


class ImportFileScanner:
    """导入目录文件扫描器。

    负责扫描导入目录直属文件，并将 Excel、Bin、MAT 文件转换成表格展示数据。

    Attributes:
        format_extensions: 文件格式到扩展名集合的映射。
    """

    format_extensions: dict[str, set[str]] = {
        "excel": {".xls", ".xlsx", ".xlsm"},
        "bin": {".bin"},
        "mat": {".mat"},
    }

    def scan(self, directories: list[str]) -> FileScanResult:
        """扫描导入目录直属文件并按数据格式分类。

        Args:
            directories: 待扫描目录路径列表；不存在或不可访问的路径会被跳过。

        Returns:
            按格式分组的表格行数据，键为 ``excel``、``bin``、``mat``，
            每行依次为文件名、修改日期、文件大小。

        Raises:
            无显式抛出异常；单个目录或文件读取失败时会跳过该项。

        Example:
            >>> scanner = ImportFileScanner()
            >>> scanner.scan([])
            {'excel': [], 'bin': [], 'mat': []}
        """
        result: FileScanResult = {key: [] for key in self.format_extensions}

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

                format_key = self._resolve_format_key(file_path)
                if format_key is None:
                    continue

                file_row = self._build_file_row(file_path)
                if file_row is not None:
                    result[format_key].append(file_row)

        for rows in result.values():
            # 默认按文件名排序，保证刷新后列表顺序稳定。
            rows.sort(key=lambda row: row[0].lower())

        return result

    def _resolve_format_key(self, file_path: Path) -> str | None:
        """根据文件扩展名解析导入格式。"""
        suffix = file_path.suffix.lower()
        for format_key, extensions in self.format_extensions.items():
            if suffix in extensions:
                return format_key
        return None

    def _build_file_row(self, file_path: Path) -> FileTableRow | None:
        """构建表格展示所需的单行文件信息。"""
        try:
            stat_result = file_path.stat()
        except OSError:
            return None

        modified_time = datetime.fromtimestamp(stat_result.st_mtime).strftime("%Y-%m-%d %H:%M")
        file_size = self._format_file_size(stat_result.st_size)
        return file_path.name, modified_time, file_size

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


def scan_import_files(directories: list[str]) -> FileScanResult:
    """使用默认扫描器扫描导入目录。

    Args:
        directories: 待扫描目录路径列表。

    Returns:
        按格式分组的表格行数据。

    Raises:
        无显式抛出异常。

    Example:
        >>> scan_import_files([])
        {'excel': [], 'bin': [], 'mat': []}
    """
    return ImportFileScanner().scan(directories)
