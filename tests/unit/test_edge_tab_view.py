"""Edge 风格标签栏绘制行为测试。"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication
from qfluentwidgets import Theme, qconfig, setTheme

from ui.components.edge_tab_view import EdgeTabBar


_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def _tab_bar() -> EdgeTabBar:
    """创建包含四个标签且完成布局的标签栏。"""
    _app()
    tab_bar = EdgeTabBar()
    tab_bar.resize(640, tab_bar.height())
    for index in range(4):
        tab_bar.addTab(f"tab-{index}", f"标签 {index}")
    tab_bar.show()
    QApplication.processEvents()
    return tab_bar


def test_separators_only_split_consecutive_unselected_tabs() -> None:
    """分隔线只应出现在相邻两侧均未选中的标签边界。"""
    tab_bar = _tab_bar()

    assert tab_bar._separatorBoundaryIndexes() == [2, 3]

    tab_bar.setCurrentIndex(2)

    assert tab_bar._separatorBoundaryIndexes() == [1]


def test_hovered_tab_hides_its_adjacent_separators() -> None:
    """悬浮标签应隐藏自身两侧分隔线并保留远端分隔线。"""
    tab_bar = _tab_bar()

    tab_bar.items[1].isHover = True

    assert tab_bar._separatorBoundaryIndexes() == [3]

    tab_bar.items[1].isHover = False
    tab_bar.items[2].isHover = True

    assert tab_bar._separatorBoundaryIndexes() == []


def test_separator_color_adapts_to_light_and_dark_themes() -> None:
    """分隔线应在明暗主题中保持与背景匹配的低对比度。"""
    _app()
    previous_theme = qconfig.theme
    tab_bar = EdgeTabBar()
    try:
        setTheme(Theme.LIGHT)
        light_color = tab_bar._separatorColor()

        setTheme(Theme.DARK)
        dark_color = tab_bar._separatorColor()

        assert light_color.getRgb() == (0, 0, 0, 20)
        assert dark_color.getRgb() == (255, 255, 255, 26)
    finally:
        setTheme(previous_theme)
