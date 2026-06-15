# -*- coding: utf-8 -*-
"""切片界面抽屉接入单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ui.interfaces.slice_interface import SliceInterface


_APP: QApplication | None = None


def _app() -> QApplication:
    """获取或创建测试用 QApplication。

    Args:
        无。

    Returns:
        QApplication: 当前进程内可用的 Qt 应用实例。

    Raises:
        无显式抛出异常。

    Example:
        >>> _app() is not None
        True
    """
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def test_slice_param_config_drawer_matches_right_column_width() -> None:
    """参数配置抽屉宽度应与右侧栏宽度一致。"""
    _app()
    interface = SliceInterface()

    assert hasattr(interface, "slice_param_config")
    assert not hasattr(interface, "slice_demo_drawer")
    assert interface.slice_param_config.drawerSize() == interface.right_column.width()


if __name__ == "__main__":
    tests = [
        test_slice_param_config_drawer_matches_right_column_width,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
