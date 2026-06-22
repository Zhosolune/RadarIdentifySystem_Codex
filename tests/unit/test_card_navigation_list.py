"""卡片导航列表组件测试。"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from ui.components.card_navigation_list import CardNavigationList


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
