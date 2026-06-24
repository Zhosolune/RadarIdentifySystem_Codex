# -*- coding: utf-8 -*-
"""切片界面抽屉接入单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtWidgets import QApplication, QLabel, QSizePolicy, QWidget
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
    assert interface.right_column.maximumWidth() == interface.RIGHT_COLUMN_MAX_WIDTH
    assert interface.slice_param_drawer.drawerSize() == interface.RIGHT_COLUMN_MAX_WIDTH
    assert interface.slice_param_drawer.contentWidget() is interface.slice_param_panel
    assert not hasattr(interface.navigation_control_card, "auto_recognize_card")
    assert interface.slice_param_panel.export_path_card is not None
    # 控制器定时器与页面存在引用环，测试结束时显式释放 Qt 对象。
    sip.delete(interface)


def test_header_title_length_does_not_change_image_column_width(
    monkeypatch: MonkeyPatch,
) -> None:
    """标题变长时图像展示列宽应保持稳定。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    interface = SliceInterface()

    try:
        interface.resize(1400, 900)
        interface.show()
        QApplication.processEvents()

        middle_column = interface.findChild(QWidget, "sliceMiddleColumn")
        assert middle_column is not None

        original_width = middle_column.width()

        interface.cluster_title_label.setText(
            "CF维聚类结果  第123/123类  总第123/123类  识别状态：未通过  "
            "这是一个非常长非常长非常长的标题，用于验证标题文本不会再撑开图像展示区域宽度"
        )
        QApplication.processEvents()

        assert middle_column.width() == original_width
        assert interface.cluster_title_label.minimumWidth() == 0
        assert (
            interface.cluster_title_label.sizePolicy().horizontalPolicy()
            == QSizePolicy.Policy.Ignored
        )

        interface.slice_title_label.setText(
            "第 123 / 123 个切片数据  原始图像  这是一个非常长非常长非常长的标题，用于验证原始图像列宽稳定"
        )
        QApplication.processEvents()

        left_column = interface.findChild(QWidget, "sliceLeftColumn")
        assert left_column is not None
        assert left_column.width() > 0
    finally:
        sip.delete(interface)


if __name__ == "__main__":
    tests = [
        test_slice_param_panel_is_mounted_in_matching_drawer,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
