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


def test_scan_reconciles_entries_with_current_directories(tmp_path: Path) -> None:
    """刷新应移除已不属于当前数据目录集合的文件并持久化结果。"""
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first_file = first_dir / "first.xlsx"
    second_file = second_dir / "second.xlsx"
    first_file.write_text("first", encoding="utf-8")
    second_file.write_text("second", encoding="utf-8")
    store = ImportFileListStore(tmp_path / "state.json")
    manager = ImportFileListManager(store)

    manager.scan([str(first_dir), str(second_dir)])
    manager.scan([str(second_dir)])

    assert [entry.path for entry in manager.files_by_type["excel"]] == [
        second_file
    ]

    # 删除最后一个数据目录后，刷新必须得到并持久化空列表。
    manager.scan([])
    assert manager.files_by_type["excel"] == []
    restored = ImportFileListManager(store)
    assert restored.files_by_type["excel"] == []

    # 目录移除不等同于单独忽略其中每个文件，重新添加后应可再次发现。
    restored.scan([str(first_dir)])
    assert [entry.path for entry in restored.files_by_type["excel"]] == [
        first_file
    ]


def test_scan_keeps_explicitly_removed_file_ignored_after_directory_readded(
    tmp_path: Path,
) -> None:
    """单独移除的文件在目录移除并重新添加后仍应保持忽略。"""
    excel_file = tmp_path / "ignored.xlsx"
    excel_file.write_text("ignored", encoding="utf-8")
    manager = ImportFileListManager(
        ImportFileListStore(tmp_path / "state.json")
    )

    manager.scan([str(tmp_path)])
    manager.remove_at("excel", 0)
    manager.scan([])
    manager.scan([str(tmp_path)])

    assert manager.files_by_type["excel"] == []


def test_entry_importability_requires_current_directory_and_existing_file(
    tmp_path: Path,
) -> None:
    """解析前校验应同时确认目录仍配置且文件仍然存在。"""
    excel_file = tmp_path / "demo.xlsx"
    excel_file.write_text("placeholder", encoding="utf-8")
    manager = ImportFileListManager(
        ImportFileListStore(tmp_path / "state.json")
    )
    manager.scan([str(tmp_path)])
    entry = manager.get_entry_at("excel", 0)

    assert entry is not None
    assert manager.is_entry_importable(entry, [str(tmp_path)])
    assert not manager.is_entry_importable(entry, [])

    excel_file.unlink()
    assert not manager.is_entry_importable(entry, [str(tmp_path)])


if __name__ == "__main__":
    tests = [
        test_get_entry_at_returns_selected_file_entry,
        test_get_entry_at_returns_none_for_invalid_row,
        test_scan_reconciles_entries_with_current_directories,
        test_scan_keeps_explicitly_removed_file_ignored_after_directory_readded,
        test_entry_importability_requires_current_directory_and_existing_file,
    ]
    import tempfile

    for test in tests:
        with tempfile.TemporaryDirectory() as temp_dir:
            test(Path(temp_dir))
        print(f"[PASS] {test.__name__}")
