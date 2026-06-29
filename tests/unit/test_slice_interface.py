# -*- coding: utf-8 -*-
"""切片界面抽屉接入单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6 import sip
from PyQt6.QtGui import QImage
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


def test_slice_interface_uses_session_scale_mode_for_image_updates(
    monkeypatch: MonkeyPatch,
) -> None:
    """切片界面重绘图像时应读取当前 session 的绘制模式。"""
    _app()
    monkeypatch.setattr(
        "ui.components.model_selection_card.collect_available_model_files",
        lambda model_type: [],
    )
    used_modes: list[str] = []

    def fake_apply_scale_mode(
        q_image: QImage,
        target_width: int,
        target_height: int,
        mode: str,
    ) -> QImage:
        """记录当前用于缩放的绘制模式。"""
        used_modes.append(mode)
        return q_image

    monkeypatch.setattr(
        "ui.adapters.image_scaler.apply_scale_mode",
        fake_apply_scale_mode,
    )

    interface = SliceInterface()
    try:
        interface.show()
        QApplication.processEvents()
        test_image = QImage(16, 16, QImage.Format.Format_RGB32)

        interface.original_cf_card.set_image(test_image)
        assert used_modes[-1] == "STRETCH"

        interface.plot_option_card.scale_mode_item.set("STRETCH_BILINEAR")
        QApplication.processEvents()
        assert used_modes[-1] == "STRETCH_BILINEAR"
    finally:
        sip.delete(interface)


if __name__ == "__main__":
    tests = [
        test_slice_param_panel_is_mounted_in_matching_drawer,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
