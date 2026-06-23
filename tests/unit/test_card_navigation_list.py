"""卡片导航列表组件测试。"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from qfluentwidgets import FluentIcon
from qfluentwidgets.common.style_sheet import isDarkTheme

from ui.components.card_navigation_list import CardNavigationList, UNIFIED_NAVIGATION_FONT_FAMILIES


_APP: QApplication | None = None


def _app() -> QApplication:
    """返回测试进程共享的 Qt 应用实例。"""
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
        return _APP
    return app


def test_card_navigation_list_switches_single_selected_item() -> None:
    """切换当前项时只保留一个选中卡片。"""
    _app()
    selected_keys: list[str] = []
    navigation_list = CardNavigationList()
    navigation_list.itemSelected.connect(selected_keys.append)

    first_item = navigation_list.add_item("import", "导入数据")
    second_item = navigation_list.add_item("slice", "切片识别")

    navigation_list.set_current_key("import")
    navigation_list.set_current_key("slice")

    assert navigation_list.current_key() == "slice"
    assert first_item.is_selected() is False
    assert second_item.is_selected() is True
    assert selected_keys == ["import", "slice"]


def test_card_navigation_item_uses_uniform_font_and_keeps_debug_prefix() -> None:
    """导航卡片应统一标题与副标题的字体族，并保留人工调试前缀。"""
    _app()
    navigation_list = CardNavigationList()

    item = navigation_list.add_item(
        "session",
        "Session A",
        "2026-06-22 12:30",
        FluentIcon.HOME,
    )
    assert item.title_label.text() == "中文测试看看字体Session A"
    assert item.subtitle_label is not None
    assert item.subtitle_label.text() == "2026-06-22 12:30"
    assert item.title_label.font().families() == UNIFIED_NAVIGATION_FONT_FAMILIES
    assert item.subtitle_label.font().families() == UNIFIED_NAVIGATION_FONT_FAMILIES
    assert item.title_label.font().pixelSize() == 14
    assert item.subtitle_label.font().pixelSize() == 12
    assert item.property("selected") is None

    item.set_selected(True)

    assert item.property("selected") is True


def test_card_navigation_item_tracks_parent_available_width() -> None:
    """导航卡片最大宽度应跟随父容器可用宽度变化。"""
    app = _app()
    navigation_list = CardNavigationList()
    navigation_list.resize(320, 240)
    navigation_list.show()

    item = navigation_list.add_item("session", "Session A", "2026-06-22 12:30")
    app.processEvents()

    expected_width = navigation_list.scroll_area.viewport().width()
    assert item.maximumWidth() == expected_width

    navigation_list.resize(260, 240)
    app.processEvents()

    expected_width = navigation_list.scroll_area.viewport().width()
    assert item.maximumWidth() == expected_width


def test_card_navigation_item_is_wrapped_by_transparent_hover_buffer() -> None:
    """导航卡片应放入透明容器，为 hover 上移动画预留裁剪缓冲。"""
    _app()
    navigation_list = CardNavigationList()

    item = navigation_list.add_item("session", "Session A", "2026-06-23 10:11")
    wrapper = item.parentWidget()
    layout_widget = navigation_list.content_layout.itemAt(0).widget()
    margins = wrapper.layout().contentsMargins()

    assert wrapper is layout_widget
    assert wrapper is not item
    assert wrapper.objectName() == "cardNavigationItemContainer"
    assert margins.top() >= 3
    assert margins.bottom() >= 3
    assert wrapper.autoFillBackground() is False


def test_card_navigation_item_selected_background_color_matches_theme_depth() -> None:
    """选中态背景色应使用主题感知的深色覆盖层。"""
    _app()
    navigation_list = CardNavigationList()
    item = navigation_list.add_item("session", "Session A", "2026-06-23 09:34")

    color = item._selected_background_color()

    assert color.alpha() == (70 if isDarkTheme() else 24)
    assert color.red() == 0


def test_card_navigation_item_hover_overlay_uses_dark_overlay_without_changing_base_card() -> None:
    """悬浮态应通过独立覆盖层加深，同时保持基础卡片底色不变。"""
    _app()
    navigation_list = CardNavigationList()
    item = navigation_list.add_item("session", "Session A", "2026-06-23 11:18")

    hover_base_color = item._hoverBackgroundColor()
    hover_overlay_color = item._interaction_overlay_color()
    normal_base_color = item._normalBackgroundColor()

    assert hover_base_color == normal_base_color
    assert hover_overlay_color.red() == 0
    assert hover_overlay_color.alpha() == 0

    # 模拟 hover 状态，验证覆盖层承担加深反馈。
    item.isHover = True
    hover_overlay_color = item._interaction_overlay_color()

    assert item._hoverBackgroundColor() == normal_base_color
    assert hover_overlay_color.red() == 0
    assert hover_overlay_color.alpha() == (36 if isDarkTheme() else 6)


def test_card_navigation_item_selected_overlay_gets_darker_on_hover() -> None:
    """选中态在悬浮时应继续加深覆盖层。"""
    _app()
    navigation_list = CardNavigationList()
    item = navigation_list.add_item("session", "Session A", "2026-06-23 11:19")

    base_selected_color = item._selected_background_color()

    item.isHover = True
    selected_hover_color = item._selected_background_color()

    assert selected_hover_color.alpha() > base_selected_color.alpha()
