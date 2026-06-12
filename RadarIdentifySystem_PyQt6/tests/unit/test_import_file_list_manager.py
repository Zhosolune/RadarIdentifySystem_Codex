# -*- coding: utf-8 -*-
"""导入文件列表管理器单元测试。

验证 UI 控制器能够通过当前标签页和表格行号取得真实文件条目，
避免从表格展示文本反推磁盘路径。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from infra.import_file_list_manager import ImportFileListManager
from infra.import_file_list_store import ImportFileListStore


def test_get_entry_at_returns_selected_file_entry(tmp_path: Path) -> None:
    """通过格式键和行号取得已扫描文件条目。"""
    excel_file = tmp_path / "demo.xlsx"
    excel_file.write_text("placeholder", encoding="utf-8")
    store = ImportFileListStore(tmp_path / "state.json")
    manager = ImportFileListManager(store)

    manager.scan([str(tmp_path)])
    entry = manager.get_entry_at("excel", 0)

    assert entry is not None
    assert entry.path == excel_file
    assert entry.format_key == "excel"


def test_get_entry_at_returns_none_for_invalid_row(tmp_path: Path) -> None:
    """行号无效时返回 None，供 UI 层提示用户重新选择。"""
    store = ImportFileListStore(tmp_path / "state.json")
    manager = ImportFileListManager(store)

    assert manager.get_entry_at("excel", -1) is None
    assert manager.get_entry_at("excel", 99) is None
    assert manager.get_entry_at("bin", 0) is None


if __name__ == "__main__":
    tests = [
        test_get_entry_at_returns_selected_file_entry,
        test_get_entry_at_returns_none_for_invalid_row,
    ]
    import tempfile

    for test in tests:
        with tempfile.TemporaryDirectory() as temp_dir:
            test(Path(temp_dir))
        print(f"[PASS] {test.__name__}")
