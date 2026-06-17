# -*- coding: utf-8 -*-
"""切片界面抽屉接入单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtWidgets import QApplication
from pytest import MonkeyPatch

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


def test_slice_param_panel_is_mounted_in_matching_drawer(
    monkeypatch: MonkeyPatch,
) -> None:
    """参数面板应挂载到与右栏同宽的独立抽屉中。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    interface = SliceInterface()

    assert hasattr(interface, "slice_param_panel")
    assert hasattr(interface, "slice_param_drawer")
    assert not hasattr(interface, "slice_param_config")
    assert interface.slice_param_drawer.drawerSize() == interface.right_column.width()
    assert interface.slice_param_drawer.contentWidget() is interface.slice_param_panel
    assert not hasattr(interface.navigation_control_card, "auto_recognize_card")
    assert interface.slice_param_panel.export_path_card is not None
    # 控制器定时器与页面存在引用环，测试结束时显式释放 Qt 对象。
    sip.delete(interface)


if __name__ == "__main__":
    tests = [
        test_slice_param_panel_is_mounted_in_matching_drawer,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
