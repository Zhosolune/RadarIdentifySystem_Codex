# -*- coding: utf-8 -*-
"""滑动抽屉组件单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QPointF, Qt, QObject, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QLabel, QWidget

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


def test_drawer_closes_when_close_button_clicked() -> None:
    """点击抽屉右上角关闭按钮时应关闭抽屉。"""
    _app()
    drawer = SlidingDrawer()

    drawer.open()
    drawer.closeButton().click()

    assert drawer.isExpanded() is False


def test_drawer_closes_when_overlay_area_clicked() -> None:
    """展开后点击抽屉面板外区域时应关闭抽屉。"""
    _app()
    drawer = SlidingDrawer(position=DrawerPosition.RIGHT, drawer_size=120)
    drawer.resize(260, 120)
    drawer.open()

    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(220, 10),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    drawer.mousePressEvent(event)

    assert drawer.isExpanded() is False


def test_drawer_closes_when_global_outside_area_clicked() -> None:
    """展开后点击组件外区域时应通过全局事件过滤关闭抽屉。"""
    _app()
    host = QWidget()
    drawer = SlidingDrawer(parent=host)

    host.resize(400, 200)
    drawer.resize(180, 120)
    drawer.open()
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(360, 80),
        QPointF(360, 80),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    drawer.eventFilter(host, event)

    assert drawer.isExpanded() is False


def test_global_outside_close_ignores_registered_trigger_widget() -> None:
    """全局外部点击关闭应忽略注册的外部唤起按钮。"""
    _app()
    host = QWidget()
    drawer = SlidingDrawer(parent=host)
    trigger = QLabel("trigger", host)

    host.resize(400, 200)
    trigger.setGeometry(320, 20, 60, 30)
    drawer.setTriggerWidget(trigger)
    drawer.open()
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(330, 25),
        QPointF(330, 25),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    drawer.eventFilter(host, event)

    assert drawer.isExpanded() is True


def test_visible_toggle_button_click_closes_expanded_drawer() -> None:
    """唤起按钮可见时，再次点击该按钮应关闭抽屉。"""
    _app()
    drawer = SlidingDrawer()

    drawer.open()
    drawer.toggleButton().click()

    assert drawer.isExpanded() is False


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
        test_drawer_closes_when_close_button_clicked,
        test_drawer_closes_when_overlay_area_clicked,
        test_drawer_closes_when_global_outside_area_clicked,
        test_global_outside_close_ignores_registered_trigger_widget,
        test_visible_toggle_button_click_closes_expanded_drawer,
        test_drawer_accepts_custom_content_widget,
        test_drawer_updates_axis_constraints,
        test_drawer_can_change_position_after_creation,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
