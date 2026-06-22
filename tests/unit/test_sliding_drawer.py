# -*- coding: utf-8 -*-
"""滑动抽屉覆盖层组件单元测试。"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QEvent, QPointF, Qt, QObject, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QLabel, QWidget
from qfluentwidgets import Theme, qconfig, setTheme

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


def _host(width: int = 400, height: int = 240) -> QWidget:
    """创建抽屉测试宿主组件。

    Args:
        width (int): 宿主组件宽度。
        height (int): 宿主组件高度。

    Returns:
        QWidget: 设置好尺寸的宿主组件。

    Raises:
        无显式抛出异常。
    """
    host = QWidget()
    host.resize(width, height)
    return host


def _disable_animation(drawer: SlidingDrawer) -> SlidingDrawer:
    """关闭测试对象动画以便同步断言几何。

    Args:
        drawer (SlidingDrawer): 需要关闭动画的抽屉实例。

    Returns:
        SlidingDrawer: 已关闭动画的抽屉实例。

    Raises:
        无显式抛出异常。
    """
    drawer.setAnimationDuration(0)
    return drawer


def _panel_style_block(drawer: SlidingDrawer) -> str:
    """提取抽屉面板的 QSS 块。

    Args:
        drawer (SlidingDrawer): 需要检查样式的抽屉实例。

    Returns:
        str: `QFrame#slidingDrawerPanel` 对应的样式片段。

    Raises:
        AssertionError: 当样式块不存在时抛出。
    """
    style_sheet = drawer.styleSheet()
    marker = "QFrame#slidingDrawerPanel {"
    start = style_sheet.find(marker)
    assert start >= 0
    end = style_sheet.find("}", start)
    assert end > start
    return style_sheet[start:end]


def test_drawer_supports_all_positions() -> None:
    """抽屉应支持上下左右四个展开方向。"""
    assert {item.name for item in DrawerPosition} == {"LEFT", "RIGHT", "TOP", "BOTTOM"}


def test_drawer_opens_as_parent_overlay_and_right_panel() -> None:
    """右侧抽屉展开后应覆盖父组件并贴右边显示面板。"""
    _app()
    host = _host()
    drawer = _disable_animation(SlidingDrawer(position=DrawerPosition.RIGHT, drawer_size=140, parent=host))

    drawer.open()

    assert drawer.isHidden() is False
    assert drawer.geometry() == host.rect()
    assert drawer.panel().geometry().x() == host.width() - 140
    assert drawer.panel().geometry().width() == 140
    assert drawer.panel().geometry().height() == host.height()


def test_drawer_places_panel_by_position() -> None:
    """抽屉面板应按展开方向贴边定位。"""
    _app()
    host = _host()
    cases = [
        (DrawerPosition.LEFT, (0, 0, 100, host.height())),
        (DrawerPosition.RIGHT, (host.width() - 100, 0, 100, host.height())),
        (DrawerPosition.TOP, (0, 0, host.width(), 100)),
        (DrawerPosition.BOTTOM, (0, host.height() - 100, host.width(), 100)),
    ]

    for position, expected in cases:
        drawer = _disable_animation(SlidingDrawer(position=position, drawer_size=100, parent=host))
        drawer.open()
        rect = drawer.panel().geometry()
        assert (rect.x(), rect.y(), rect.width(), rect.height()) == expected
        drawer.close()


def test_drawer_expanded_state_and_signals() -> None:
    """抽屉应支持方法和信号槽式展开状态控制。"""
    _app()
    host = _host()
    drawer = _disable_animation(SlidingDrawer(position=DrawerPosition.LEFT, parent=host))
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
    host = _host()
    drawer = _disable_animation(SlidingDrawer(parent=host))
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
    host = _host()
    drawer = _disable_animation(SlidingDrawer(parent=host))

    assert drawer.isToggleButtonVisible() is False
    drawer.setToggleButtonVisible(True)

    assert drawer.isToggleButtonVisible() is True
    assert drawer.toggleButton().isHidden() is False


def test_drawer_closes_when_close_button_clicked() -> None:
    """点击抽屉右上角关闭按钮时应关闭抽屉。"""
    _app()
    host = _host()
    drawer = _disable_animation(SlidingDrawer(parent=host))

    drawer.open()
    drawer.closeButton().click()

    assert drawer.isExpanded() is False
    assert drawer.isHidden() is True


def test_drawer_closes_when_overlay_area_clicked() -> None:
    """展开后点击抽屉面板外区域时应关闭抽屉。"""
    _app()
    host = _host()
    drawer = _disable_animation(SlidingDrawer(position=DrawerPosition.RIGHT, drawer_size=120, parent=host))
    drawer.open()

    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(20, 20),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    drawer.mousePressEvent(event)

    assert drawer.isExpanded() is False


def test_drawer_trigger_area_click_closes_without_reopening() -> None:
    """点击外部唤起按钮区域时应关闭抽屉，不被遮罩逻辑误判。"""
    _app()
    host = _host()
    trigger = QLabel("trigger", host)
    trigger.setGeometry(20, 20, 80, 32)
    drawer = SlidingDrawer(position=DrawerPosition.RIGHT, parent=host)
    drawer.setAnimationDuration(0)
    drawer.setTriggerWidget(trigger)
    drawer.open()

    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(30, 26),
        QPointF(30, 26),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    drawer.mousePressEvent(event)

    assert drawer.isExpanded() is False


def test_drawer_accepts_custom_content_widget() -> None:
    """抽屉内容区应允许替换为任意 QWidget。"""
    _app()
    host = _host()
    drawer = _disable_animation(SlidingDrawer(parent=host))
    label = QLabel("content")

    drawer.setContentWidget(label)

    assert drawer.contentWidget() is label
    assert drawer.contentLayout() is None


def test_drawer_can_change_position_after_creation() -> None:
    """抽屉创建后应允许切换展开方向。"""
    _app()
    host = _host()
    drawer = _disable_animation(SlidingDrawer(position=DrawerPosition.LEFT, drawer_size=160, parent=host))

    drawer.open()
    drawer.setPosition(DrawerPosition.BOTTOM)

    assert drawer.position() is DrawerPosition.BOTTOM
    assert drawer.panel().geometry().y() == host.height() - 160
    assert drawer.panel().geometry().height() == 160


def test_drawer_uses_soft_shadow_and_slower_animation() -> None:
    """抽屉应使用较慢的默认动画且不绘制外部遮罩。"""
    _app()
    host = _host()
    drawer = SlidingDrawer(parent=host)

    assert drawer.animationDuration() >= 320
    assert drawer.maskAlpha() == 0


def test_drawer_uses_component_panel_background_and_soft_shadow() -> None:
    """抽屉应使用组件库面板背景并进一步柔化阴影。"""
    _app()
    previous_theme = qconfig.theme
    try:
        setTheme(Theme.LIGHT)
        host = _host()
        drawer = SlidingDrawer(parent=host)
        shadow = drawer.panel().graphicsEffect()

        assert drawer.maskAlpha() == 0
        assert shadow.blurRadius() == 35
        assert shadow.xOffset() == 0
        assert shadow.yOffset() == 8
        assert shadow.color().alpha() == 30
        assert drawer.edgeShadowAlpha() == 0
        assert "flyout.py" in drawer.shadowEffectSource()
        assert drawer.lightPanelBackgroundColor() == "rgb(243, 243, 243)"
        assert "navigation_interface.qss" in drawer.panelBackgroundColorSource()
        assert "border: none" in _panel_style_block(drawer)
    finally:
        setTheme(previous_theme)


def test_drawer_adapts_to_dark_theme() -> None:
    """抽屉应在暗色主题下使用组件库暗色面板样式。"""
    _app()
    previous_theme = qconfig.theme
    try:
        setTheme(Theme.DARK)
        host = _host()
        drawer = SlidingDrawer(parent=host)
        shadow = drawer.panel().graphicsEffect()
        style_sheet = drawer.styleSheet()

        assert drawer.darkPanelBackgroundColor() == "rgb(32, 32, 32)"
        assert drawer.darkPanelBackgroundColor() in style_sheet
        assert "rgb(255, 255, 255)" in style_sheet
        assert "border: none" in _panel_style_block(drawer)
        assert shadow.color().alpha() == 80
    finally:
        setTheme(previous_theme)


def test_drawer_updates_existing_instance_when_theme_changes() -> None:
    """抽屉实例应在组件库主题切换信号触发后刷新样式和阴影。"""
    _app()
    previous_theme = qconfig.theme
    try:
        setTheme(Theme.LIGHT)
        host = _host()
        drawer = SlidingDrawer(parent=host)

        assert drawer.lightPanelBackgroundColor() in drawer.styleSheet()
        assert drawer.panel().graphicsEffect().color().alpha() == 30

        setTheme(Theme.DARK)

        assert drawer.darkPanelBackgroundColor() in drawer.styleSheet()
        assert drawer.lightPanelBackgroundColor() not in drawer.styleSheet()
        assert drawer.panel().graphicsEffect().color().alpha() == 80
        assert "border: none" in _panel_style_block(drawer)
    finally:
        setTheme(previous_theme)


def test_style_change_event_does_not_reapply_stylesheet_recursively() -> None:
    """StyleChange 事件不应触发 setStyleSheet 递归。"""
    _app()
    host = _host()
    drawer = SlidingDrawer(parent=host)

    handled = drawer.event(QEvent(QEvent.Type.StyleChange))

    assert handled in (True, False)


if __name__ == "__main__":
    tests = [
        test_drawer_supports_all_positions,
        test_drawer_opens_as_parent_overlay_and_right_panel,
        test_drawer_places_panel_by_position,
        test_drawer_expanded_state_and_signals,
        test_drawer_accepts_external_signal_connections,
        test_drawer_can_hide_toggle_button,
        test_drawer_closes_when_close_button_clicked,
        test_drawer_closes_when_overlay_area_clicked,
        test_drawer_trigger_area_click_closes_without_reopening,
        test_drawer_accepts_custom_content_widget,
        test_drawer_can_change_position_after_creation,
        test_drawer_uses_soft_shadow_and_slower_animation,
        test_drawer_uses_component_panel_background_and_soft_shadow,
        test_drawer_adapts_to_dark_theme,
        test_drawer_updates_existing_instance_when_theme_changes,
        test_style_change_event_does_not_reapply_stylesheet_recursively,
    ]
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
