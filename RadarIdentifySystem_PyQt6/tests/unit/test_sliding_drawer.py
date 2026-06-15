# -*- coding: utf-8 -*-
"""滑动抽屉组件单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QLabel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ui.components.sliding_drawer import DrawerPosition, SlidingDrawer


_APP: QApplication | None = None


class _SignalEmitter(QObject):
    """测试用外部信号发射器。"""

    openRequested = pyqtSignal()
    closeRequested = pyqtSignal()
    toggleRequested = pyqtSignal()


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


def test_drawer_supports_all_positions() -> None:
    """抽屉应支持上下左右四个展开方向。"""
    assert {item.name for item in DrawerPosition} == {"LEFT", "RIGHT", "TOP", "BOTTOM"}


def test_drawer_expanded_state_and_signals() -> None:
    """抽屉应支持方法和信号槽式展开状态控制。"""
    _app()
    drawer = SlidingDrawer(position=DrawerPosition.LEFT)
    states: list[bool] = []
    opened: list[bool] = []
    closed: list[bool] = []

    drawer.expandedChanged.connect(states.append)
    drawer.opened.connect(lambda: opened.append(True))
    drawer.closed.connect(lambda: closed.append(True))

    assert drawer.isExpanded() is False
    drawer.open()
    assert drawer.isExpanded() is True
    drawer.close()
    assert drawer.isExpanded() is False
    drawer.toggle()
    assert drawer.isExpanded() is True

    assert states == [True, False, True]
    assert opened == [True, True]
    assert closed == [True]


def test_drawer_accepts_external_signal_connections() -> None:
    """抽屉应支持外部信号连接控制展开、关闭与切换。"""
    _app()
    drawer = SlidingDrawer()
    emitter = _SignalEmitter()

    emitter.openRequested.connect(drawer.open)
    emitter.closeRequested.connect(drawer.close)
    emitter.toggleRequested.connect(drawer.toggle)

    emitter.openRequested.emit()
    assert drawer.isExpanded() is True
    emitter.closeRequested.emit()
    assert drawer.isExpanded() is False
    emitter.toggleRequested.emit()
    assert drawer.isExpanded() is True


def test_drawer_can_hide_toggle_button() -> None:
    """抽屉应支持隐藏展开按钮。"""
    _app()
    drawer = SlidingDrawer()

    assert drawer.isToggleButtonVisible() is True
    drawer.setToggleButtonVisible(False)

    assert drawer.isToggleButtonVisible() is False
    assert drawer.toggleButton().isVisible() is False


def test_drawer_accepts_custom_content_widget() -> None:
    """抽屉内容区应允许替换为任意 QWidget。"""
    _app()
    drawer = SlidingDrawer()
    label = QLabel("content")

    drawer.setContentWidget(label)

    assert drawer.contentWidget() is label
    assert drawer.contentLayout() is None


def test_drawer_updates_axis_constraints() -> None:
    """抽屉展开尺寸应随方向作用在对应轴上。"""
    _app()
    left = SlidingDrawer(position=DrawerPosition.LEFT, drawer_size=180)
    top = SlidingDrawer(position=DrawerPosition.TOP, drawer_size=96)

    left.open()
    top.open()

    assert left.panel().maximumWidth() == 180
    assert top.panel().maximumHeight() == 96


def test_drawer_can_change_position_after_creation() -> None:
    """抽屉创建后应允许切换展开方向。"""
    _app()
    drawer = SlidingDrawer(position=DrawerPosition.LEFT, drawer_size=160)

    drawer.open()
    drawer.setPosition(DrawerPosition.BOTTOM)

    assert drawer.position() is DrawerPosition.BOTTOM
    assert drawer.panel().maximumHeight() == 160
    assert drawer.panel().maximumWidth() == 16777215


if __name__ == "__main__":
    tests = [
        test_drawer_supports_all_positions,
        test_drawer_expanded_state_and_signals,
        test_drawer_accepts_external_signal_connections,
        test_drawer_can_hide_toggle_button,
        test_drawer_accepts_custom_content_widget,
        test_drawer_updates_axis_constraints,
        test_drawer_can_change_position_after_creation,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
