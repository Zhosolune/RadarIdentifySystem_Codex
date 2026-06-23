"""主页布局测试。"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication, QSizePolicy, QWidget

from ui.interfaces.home_interface import HomeInterface


_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def test_home_interface_uses_fixed_columns_without_root_scroll_area() -> None:
    """主页应使用左右非滚动根布局，并将右侧拆为上下双卡片。"""
    _app()
    interface = HomeInterface()

    left_layout = interface.left_column.layout()
    right_layout = interface.right_column.layout()

    assert interface.findChild(QWidget, "homeLeftScrollArea") is None
    assert left_layout.count() == 3
    assert interface.dashboard_panel.minimumHeight() == 300
    assert interface.dashboard_panel.maximumHeight() == 300
    assert interface.import_panel.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    assert right_layout.count() == 2
    assert right_layout.stretch(0) == 1
    assert right_layout.stretch(1) == 1
    assert interface.session_placeholder_card.objectName() == "homeRightPlaceholderCard"
